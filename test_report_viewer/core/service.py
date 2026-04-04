"""
Simple service layer that coordinates the core functionality.
No complex abstractions - just straightforward business logic.
"""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Project, TestRun, Test, TestResult, Status
from .scanner import scan_projects
from .parser import parse_junit_xml

class TestReportService:
    """Simple service that handles all test report operations."""

    def __init__(self, session):
        self.session = session

    # Project operations
    def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        return self.session.query(Project).all()

    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        return self.session.query(Project).filter_by(id=project_id).first()

    def get_project_by_identifier(self, identifier: str) -> Optional[Project]:
        """Get project by identifier."""
        return self.session.query(Project).filter_by(identifier=identifier).first()

    def create_or_update_project(self, name: str, identifier: str = None, out_dir: str = "") -> Project:
        """Create or update a project."""
        if not identifier:
            identifier = self._slugify(name)

        # Check if exists
        project = self.session.query(Project).filter_by(identifier=identifier).first()
        if project:
            project.name = name
            project.out_dir = out_dir
        else:
            # Ensure unique identifier
            base = identifier
            i = 2
            while self.session.query(Project).filter_by(identifier=identifier).first():
                identifier = f"{base}-{i}"
                i += 1

            project = Project(name=name, identifier=identifier, out_dir=out_dir)
            self.session.add(project)

        self.session.commit()
        return project

    def delete_project(self, project_id: int):
        """Delete a project."""
        project = self.session.query(Project).filter_by(id=project_id).first()
        if project:
            self.session.delete(project)
            self.session.commit()

    # Scanning and parsing
    def scan_and_parse_new_files(self) -> List[str]:
        """Scan for new files and parse them."""
        new_files = scan_projects(self.session)
        processed = []

        for project, file_path in new_files:
            try:
                parse_junit_xml(self.session, project, file_path)
                processed.append(file_path)
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

        return processed

    # View data for web/CLI
    def get_project_summary(self, project_id: int, subpath: str = "", summary_runs: int = 10,
                          filters: List[tuple] = None, trim: bool = False) -> Dict[str, Any]:
        """Get project summary data."""
        project = self.get_project_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Current path
        current_path = "/" + (subpath or "").strip("/")
        if current_path == "//" or current_path == "/":
            current_path = "/"

        # Get test runs
        runs = (self.session.query(TestRun)
                .filter_by(project_id=project_id)
                .order_by(TestRun.run_at.desc())
                .limit(summary_runs)
                .all())
        runs = list(reversed(runs))  # oldest to newest

        # Get tests and apply filters
        all_tests = (self.session.query(Test)
                    .filter_by(project_id=project_id)
                    .order_by(Test.name.asc())
                    .all())

        tests = [t for t in all_tests if self._within_prefix(t.name, current_path)]

        # Apply regex filters
        if filters:
            for ftype, pattern in filters:
                if ftype == "include":
                    tests = [t for t in tests if self._matches_filter(t.name, pattern)]
                elif ftype == "exclude":
                    tests = [t for t in tests if not self._matches_filter(t.name, pattern)]

        # Common path prefix for the optional trimmed path display.
        prefix_parts = self._common_prefix([
            self._path_parts_from_test_name(t.name)
            for t in tests
        ])

        # Build matrix
        matrix = []
        for test in tests:
            row_results = []
            for run in runs:
                result = (self.session.query(TestResult)
                         .filter_by(test_id=test.id, testrun_id=run.id)
                         .first())
                row_results.append(result)
            matrix.append((test, row_results))

        # Latest run counts
        latest_counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        if runs:
            latest_results = (self.session.query(TestResult)
                             .filter_by(testrun_id=runs[-1].id)
                             .all())
            for result in latest_results:
                latest_counts[result.status.value] += 1

        # Breadcrumbs
        breadcrumbs = self._build_breadcrumbs(current_path)

        return {
            "project": project,
            "runs": runs,
            "tests": tests,
            "matrix": matrix,
            "latest_counts": latest_counts,
            "current_path": current_path,
            "breadcrumbs": breadcrumbs,
            "filters": filters or [],
            "ordered_filters": filters or [],
            "trim": trim,
            "prefix_parts": prefix_parts
        }

    def get_test_run_details(self, project_id: int, run_id: int) -> Dict[str, Any]:
        """Get test run details."""
        project = self.get_project_by_id(project_id)
        run = self.session.query(TestRun).filter_by(id=run_id, project_id=project_id).first()

        if not project or not run:
            raise ValueError("Project or run not found")

        results = (self.session.query(TestResult)
                  .filter_by(testrun_id=run_id)
                  .join(Test)
                  .order_by(Test.name.asc())
                  .all())

        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for result in results:
            counts[result.status.value] += 1

        return {
            "project": project,
            "run": run,
            "results": results,
            "counts": counts
        }

    def get_test_details(self, project_id: int, test_id: int) -> Dict[str, Any]:
        """Get test details."""
        project = self.get_project_by_id(project_id)
        test = self.session.query(Test).filter_by(id=test_id, project_id=project_id).first()

        if not project or not test:
            raise ValueError("Project or test not found")

        results = (self.session.query(TestResult)
                  .filter_by(test_id=test_id)
                  .join(TestRun)
                  .order_by(TestRun.run_at.asc())
                  .all())

        # Chart points
        chart_points = [
            {
                "x": r.testrun.run_at.strftime("%Y-%m-%d %H:%M:%S"),
                "y": r.status.value.capitalize()
            }
            for r in results
        ]

        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for result in results:
            counts[result.status.value] += 1

        breadcrumbs = self._build_breadcrumbs_for_test(test.name)

        return {
            "project": project,
            "test": test,
            "results": results,
            "chart_points": chart_points,
            "counts": counts,
            "breadcrumbs": breadcrumbs
        }

    def get_project_list_with_stats(self, order: str = "name") -> Dict[str, Any]:
        """Get project list with statistics."""
        projects = self.get_all_projects()

        def get_latest_stats(p):
            run = (self.session.query(TestRun)
                  .filter_by(project_id=p.id)
                  .order_by(TestRun.run_at.desc())
                  .first())
            if not run:
                return (None, 0, 0)

            results = self.session.query(TestResult).filter_by(testrun_id=run.id).all()
            passed = sum(1 for r in results if r.status == Status.passed)
            total = run.total or len(results)
            return (run.run_at, passed, total)

        stats = {p.id: get_latest_stats(p) for p in projects}

        # Sort projects
        if order == "date":
            projects.sort(key=lambda p: stats[p.id][0] or datetime.min, reverse=True)
        elif order == "id":
            projects.sort(key=lambda p: p.id)
        else:  # name
            projects.sort(key=lambda p: (p.name or "").lower())

        # Add tooltips
        decorated = []
        for p in projects:
            run_at, passed, total = stats[p.id]
            tooltip = f"ID: {p.id}\nIdentifier: {p.identifier}\nLast: {passed}/{total} passed"
            decorated.append((p, tooltip))

        return {
            "projects": decorated,
            "order_mode": order
        }

    def choose_default_project(self, config: dict = None) -> Optional[Project]:
        """Choose default project based on config."""
        config = config or {}

        # Try by ID first
        if config.get("default_project_id"):
            project = self.get_project_by_id(config["default_project_id"])
            if project:
                return project

        # Try by identifier
        if config.get("default_project_identifier"):
            project = self.get_project_by_identifier(config["default_project_identifier"])
            if project:
                return project

        # Fall back to first project
        projects = self.get_all_projects()
        return projects[0] if projects else None

    # Helper methods
    def _slugify(self, s: str) -> str:
        """Convert string to URL-friendly identifier."""
        s = re.sub(r"\s+", "-", (s or "").strip())
        s = re.sub(r"[^a-zA-Z0-9._-]", "-", s)
        return re.sub(r"-{2,}", "-", s).strip("-").lower() or "project"

    def _within_prefix(self, test_name: str, current_path: str) -> bool:
        """Check if test falls under current path."""
        if not current_path or current_path == "/":
            return True
        pathy = "/" + test_name.replace(".", "/")
        return pathy == current_path or pathy.startswith(current_path.rstrip("/") + "/")

    def _matches_filter(self, test_name: str, pattern: str) -> bool:
        """Check if test name matches filter pattern."""
        try:
            regex = re.compile(pattern)
            dotted = test_name
            pathy = "/" + test_name.replace(".", "/")
            return bool(regex.search(dotted) or regex.search(pathy))
        except re.error:
            return False

    def _build_breadcrumbs(self, current_path: str) -> List[tuple]:
        """Build breadcrumbs for current path."""
        breadcrumbs = []
        if current_path != "/":
            parts = [p for p in current_path.strip("/").split("/") if p]
            acc = ""
            for part in parts:
                acc = acc + "/" + part
                breadcrumbs.append((part, acc.strip("/")))
        return breadcrumbs

    def _build_breadcrumbs_for_test(self, test_name: str) -> List[tuple]:
        """Build breadcrumbs for test path."""
        parts = ("/" + test_name.replace(".", "/")).strip("/").split("/")
        breadcrumbs = []
        acc = ""
        for part in parts:
            acc = acc + "/" + part
            breadcrumbs.append((part, acc.strip("/")))
        return breadcrumbs

    def _path_parts_from_test_name(self, test_name: str) -> List[str]:
        """Convert a dotted test name to path parts."""
        return ("/" + test_name.replace(".", "/")).strip("/").split("/")

    def _common_prefix(self, parts_list: List[List[str]]) -> List[str]:
        """Return the shared leading path parts for a list of paths."""
        if not parts_list:
            return []

        prefix = []
        for grouped_parts in zip(*parts_list):
            first = grouped_parts[0]
            if all(part == first for part in grouped_parts):
                prefix.append(first)
            else:
                break
        return prefix
