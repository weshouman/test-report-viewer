import os
import xml.etree.ElementTree as ET
from datetime import datetime
from .models import Project, TestRun, Test, TestResult, Status

def parse_junit_xml(session, project: Project, file_path: str) -> TestRun:
    """Parse a JUnit XML file and store the results."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Determine run_at from filename if it looks like TEST-<...>-<timestamp>.xml
    run_at = datetime.utcnow()
    base = os.path.basename(file_path)
    try:
        # try to pick the last numeric group in the filename as timestamp (YYYYMMDDHHMMSS)
        stamp = ''.join(filter(str.isdigit, os.path.splitext(base)[0].split('-')[-1]))
        if len(stamp) >= 14:
            run_at = datetime.strptime(stamp[:14], "%Y%m%d%H%M%S")
    except Exception:
        pass

    testrun = TestRun(project_id=project.id, run_at=run_at, filename=os.path.abspath(file_path))

    # Handle either <testsuite> root or <testsuites>
    testsuites = []
    if root.tag == "testsuite":
        testsuites = [root]
    elif root.tag == "testsuites":
        testsuites = list(root.findall("testsuite"))
    else:
        # try namespace-insensitive approach
        tag = root.tag.split('}')[-1]
        if tag == "testsuite":
            testsuites = [root]
        elif tag == "testsuites":
            testsuites = list(root.findall(".//{*}testsuite"))

    total = failures = errors = skipped = 0

    session.add(testrun)
    session.flush()  # to get testrun.id

    for suite in testsuites:
        for tc in suite.findall("testcase"):
            name = tc.get("name") or "unnamed"
            classname = tc.get("classname") or (suite.get("name") or "")
            time_attr = tc.get("time") or "0"
            try:
                t_time = float(time_attr)
            except Exception:
                t_time = 0.0

            test = session.query(Test).filter_by(project_id=project.id, name=f"{classname}.{name}").first()
            if not test:
                test = Test(project_id=project.id, name=f"{classname}.{name}", classname=classname)
                session.add(test)
                session.flush()

            status = Status.passed
            message = None
            if tc.find("failure") is not None:
                status = Status.failed
                f = tc.find("failure")
                message = (f.get("message") or "") + "\n" + (f.text or "")
            elif tc.find("error") is not None:
                status = Status.error
                e = tc.find("error")
                message = (e.get("message") or "") + "\n" + (e.text or "")
            elif tc.find("skipped") is not None:
                status = Status.skipped
                s = tc.find("skipped")
                message = (s.get("message") or "") + "\n" + (s.text or "")

            tr = TestResult(test_id=test.id, testrun_id=testrun.id, status=status, time=t_time, message=message or "")

            # Regression detection: failed/error after last non-skipped was passed
            prev = (session.query(TestResult)
                    .filter(TestResult.test_id == test.id, TestResult.testrun_id != testrun.id)
                    .join(TestRun)
                    .order_by(TestRun.run_at.desc())
                    .first())
            if prev and prev.status == Status.passed and status in (Status.failed, Status.error):
                tr.regression = True

            session.add(tr)

            total += 1
            if status == Status.failed:
                failures += 1
            elif status == Status.error:
                errors += 1
            elif status == Status.skipped:
                skipped += 1

    testrun.total = total
    testrun.failures = failures
    testrun.errors = errors
    testrun.skipped = skipped

    session.commit()
    return testrun