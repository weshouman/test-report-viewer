"""
Unit tests for the core JUnit XML parser functionality.
Tests the parser module independent of the web interface.
"""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_report_viewer.core.models import Project, TestRun, Test, TestResult, Status, create_database
from test_report_viewer.core.parser import parse_junit_xml


class ParserTestCase(unittest.TestCase):
    """Test cases for JUnit XML parsing functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.engine, self.SessionLocal = create_database(f'sqlite:///{self.db_path}')
        self.session = self.SessionLocal()

        self.project = Project(
            name="Test Project",
            identifier="test-project",
            out_dir="/tmp/test"
        )
        self.session.add(self.project)
        self.session.commit()

    def tearDown(self):
        """Clean up after each test method."""
        self.session.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def create_junit_xml(self, content):
        """Helper to create a temporary JUnit XML file."""
        fd, path = tempfile.mkstemp(suffix='.xml')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return path

    def test_parse_simple_junit_xml(self):
        """Test parsing a simple JUnit XML file."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="TestSuite" tests="2" failures="1" errors="0" skipped="0" time="0.123">
    <testcase name="test_success" classname="TestClass" time="0.050">
    </testcase>
    <testcase name="test_failure" classname="TestClass" time="0.073">
        <failure message="AssertionError: Expected 1 but got 2">
            Test failed because assertion was false
        </failure>
    </testcase>
</testsuite>'''

        xml_path = self.create_junit_xml(xml_content)

        try:
            testrun = parse_junit_xml(self.session, self.project, xml_path)

            # Verify test run was created
            self.assertIsNotNone(testrun.id)
            self.assertEqual(testrun.project_id, self.project.id)
            self.assertEqual(testrun.total, 2)
            self.assertEqual(testrun.failures, 1)
            self.assertEqual(testrun.errors, 0)
            self.assertEqual(testrun.skipped, 0)

            # Verify tests and results were created
            tests = self.session.query(Test).filter_by(project_id=self.project.id).all()
            self.assertEqual(len(tests), 2)

            results = self.session.query(TestResult).filter_by(testrun_id=testrun.id).all()
            self.assertEqual(len(results), 2)

            # Check specific test results
            success_result = next(r for r in results if r.test.name.endswith("test_success"))
            failure_result = next(r for r in results if r.test.name.endswith("test_failure"))

            self.assertEqual(success_result.status, Status.passed)
            self.assertEqual(failure_result.status, Status.failed)
            self.assertIn("AssertionError", failure_result.message)

        finally:
            os.unlink(xml_path)

    def test_parse_junit_xml_with_errors_and_skipped(self):
        """Test parsing JUnit XML with errors and skipped tests."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="TestSuite" tests="3" failures="0" errors="1" skipped="1" time="0.100">
    <testcase name="test_error" classname="TestClass" time="0.050">
        <error message="RuntimeError: Something went wrong">
            Stack trace here
        </error>
    </testcase>
    <testcase name="test_skipped" classname="TestClass" time="0.000">
        <skipped message="Test was skipped">
            Skipped because condition not met
        </skipped>
    </testcase>
    <testcase name="test_success" classname="TestClass" time="0.050">
    </testcase>
</testsuite>'''

        xml_path = self.create_junit_xml(xml_content)

        try:
            testrun = parse_junit_xml(self.session, self.project, xml_path)

            self.assertEqual(testrun.total, 3)
            self.assertEqual(testrun.failures, 0)
            self.assertEqual(testrun.errors, 1)
            self.assertEqual(testrun.skipped, 1)

            results = self.session.query(TestResult).filter_by(testrun_id=testrun.id).all()
            status_counts = {}
            for result in results:
                status_counts[result.status.value] = status_counts.get(result.status.value, 0) + 1

            self.assertEqual(status_counts.get('passed', 0), 1)
            self.assertEqual(status_counts.get('error', 0), 1)
            self.assertEqual(status_counts.get('skipped', 0), 1)

        finally:
            os.unlink(xml_path)

    def test_parse_testsuites_xml(self):
        """Test parsing JUnit XML with multiple test suites."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
    <testsuite name="Suite1" tests="1" failures="0" errors="0" skipped="0" time="0.050">
        <testcase name="test_one" classname="Class1" time="0.050">
        </testcase>
    </testsuite>
    <testsuite name="Suite2" tests="1" failures="0" errors="0" skipped="0" time="0.075">
        <testcase name="test_two" classname="Class2" time="0.075">
        </testcase>
    </testsuite>
</testsuites>'''

        xml_path = self.create_junit_xml(xml_content)

        try:
            testrun = parse_junit_xml(self.session, self.project, xml_path)

            self.assertEqual(testrun.total, 2)

            tests = self.session.query(Test).filter_by(project_id=self.project.id).all()
            self.assertEqual(len(tests), 2)

            test_names = [t.name for t in tests]
            self.assertIn("Class1.test_one", test_names)
            self.assertIn("Class2.test_two", test_names)

        finally:
            os.unlink(xml_path)

    def test_parse_timestamp_from_filename(self):
        """Test extracting timestamp from filename."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="TestSuite" tests="1" failures="0" errors="0" skipped="0" time="0.050">
    <testcase name="test_one" classname="TestClass" time="0.050">
    </testcase>
</testsuite>'''

        # Create file with timestamp in name
        fd, xml_path = tempfile.mkstemp(
            suffix='-20240315142030.xml',  # March 15, 2024, 14:20:30
            prefix='TEST-results-'
        )
        with os.fdopen(fd, 'w') as f:
            f.write(xml_content)

        try:
            testrun = parse_junit_xml(self.session, self.project, xml_path)

            # Check that timestamp was parsed correctly
            expected_time = datetime(2024, 3, 15, 14, 20, 30)
            self.assertEqual(testrun.run_at, expected_time)

        finally:
            os.unlink(xml_path)

    def test_invalid_xml_handling(self):
        """Test handling of invalid XML content."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<invalid>
    <not_a_testsuite>
    </not_a_testsuite>
</invalid>'''

        xml_path = self.create_junit_xml(xml_content)

        try:
            testrun = parse_junit_xml(self.session, self.project, xml_path)

            # Should create testrun but with no tests
            self.assertIsNotNone(testrun.id)
            self.assertEqual(testrun.total, 0)

            tests = self.session.query(Test).filter_by(project_id=self.project.id).all()
            self.assertEqual(len(tests), 0)

        finally:
            os.unlink(xml_path)


if __name__ == '__main__':
    unittest.main()