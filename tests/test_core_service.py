"""
Unit tests for the core service layer.
Tests business logic and use case coordination.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_report_viewer.core.models import Project, TestRun, Test, TestResult, Status, create_database
from test_report_viewer.core.service import TestReportService


class ServiceTestCase(unittest.TestCase):
    """Test cases for the core service layer."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.engine, self.SessionLocal = create_database(f'sqlite:///{self.db_path}')
        self.session = self.SessionLocal()
        self.service = TestReportService(self.session)

    def tearDown(self):
        """Clean up after each test method."""
        self.session.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def create_test_data(self):
        """Helper method to create test data."""
        project = Project(
            name="Test Project",
            identifier="test-project",
            out_dir="/tmp/test"
        )
        self.session.add(project)
        self.session.commit()

        # Add a test run
        test_run = TestRun(
            project_id=project.id,
            run_at=datetime.now(),
            filename="/tmp/test-run.xml",
            total=3,
            failures=1,
            errors=0,
            skipped=1
        )
        self.session.add(test_run)
        self.session.commit()

        # Add some tests
        test1 = Test(project_id=project.id, name="test.example.test_one")
        test2 = Test(project_id=project.id, name="test.example.test_two")
        test3 = Test(project_id=project.id, name="test.example.test_three")
        self.session.add_all([test1, test2, test3])
        self.session.commit()

        # Add test results
        result1 = TestResult(
            test_id=test1.id, testrun_id=test_run.id,
            status=Status.passed, time=0.123
        )
        result2 = TestResult(
            test_id=test2.id, testrun_id=test_run.id,
            status=Status.failed, time=0.456,
            message="AssertionError: Expected 1 but got 2"
        )
        result3 = TestResult(
            test_id=test3.id, testrun_id=test_run.id,
            status=Status.skipped, time=0.0,
            message="Skipped due to configuration"
        )
        self.session.add_all([result1, result2, result3])
        self.session.commit()

        return project.id, test_run.id, [test1.id, test2.id, test3.id]

    def test_project_creation(self):
        """Test project creation through service."""
        project = self.service.create_or_update_project(
            name="New Project",
            identifier="new-project",
            out_dir="/tmp/new"
        )

        self.assertIsNotNone(project.id)
        self.assertEqual(project.name, "New Project")
        self.assertEqual(project.identifier, "new-project")
        self.assertEqual(project.out_dir, "/tmp/new")

    def test_project_update(self):
        """Test project update through service."""
        # Create project
        project = self.service.create_or_update_project(
            name="Original Name",
            identifier="test-project",
            out_dir="/tmp/original"
        )

        original_id = project.id

        # Update project
        updated_project = self.service.create_or_update_project(
            name="Updated Name",
            identifier="test-project",
            out_dir="/tmp/updated"
        )

        self.assertEqual(updated_project.id, original_id)  # Same project
        self.assertEqual(updated_project.name, "Updated Name")
        self.assertEqual(updated_project.out_dir, "/tmp/updated")

    def test_get_project_summary(self):
        """Test project summary generation."""
        project_id, run_id, test_ids = self.create_test_data()

        summary = self.service.get_project_summary(project_id)

        self.assertEqual(summary['project'].id, project_id)
        self.assertEqual(len(summary['runs']), 1)
        self.assertEqual(len(summary['tests']), 3)
        self.assertEqual(len(summary['matrix']), 3)

        # Check counts
        self.assertEqual(summary['latest_counts']['passed'], 1)
        self.assertEqual(summary['latest_counts']['failed'], 1)
        self.assertEqual(summary['latest_counts']['skipped'], 1)

    def test_get_project_summary_with_filters(self):
        """Test project summary with filtering."""
        project_id, run_id, test_ids = self.create_test_data()

        # Test include filter
        summary = self.service.get_project_summary(
            project_id,
            filters=[("include", "test_one")]
        )

        self.assertEqual(len(summary['tests']), 1)
        self.assertEqual(summary['tests'][0].name, "test.example.test_one")

        # Test exclude filter
        summary = self.service.get_project_summary(
            project_id,
            filters=[("exclude", "test_one")]
        )

        self.assertEqual(len(summary['tests']), 2)
        test_names = [t.name for t in summary['tests']]
        self.assertNotIn("test.example.test_one", test_names)

    def test_get_test_run_details(self):
        """Test test run details retrieval."""
        project_id, run_id, test_ids = self.create_test_data()

        details = self.service.get_test_run_details(project_id, run_id)

        self.assertEqual(details['project'].id, project_id)
        self.assertEqual(details['run'].id, run_id)
        self.assertEqual(len(details['results']), 3)
        self.assertEqual(details['counts']['passed'], 1)
        self.assertEqual(details['counts']['failed'], 1)
        self.assertEqual(details['counts']['skipped'], 1)

    def test_get_test_details(self):
        """Test individual test details retrieval."""
        project_id, run_id, test_ids = self.create_test_data()
        test_id = test_ids[0]

        details = self.service.get_test_details(project_id, test_id)

        self.assertEqual(details['project'].id, project_id)
        self.assertEqual(details['test'].id, test_id)
        self.assertEqual(len(details['results']), 1)
        self.assertEqual(len(details['chart_points']), 1)
        self.assertEqual(details['counts']['passed'], 1)

    def test_project_list_with_stats(self):
        """Test project list with statistics."""
        project_id, run_id, test_ids = self.create_test_data()

        project_list = self.service.get_project_list_with_stats()

        self.assertEqual(len(project_list['projects']), 1)
        project, tooltip = project_list['projects'][0]
        self.assertEqual(project.id, project_id)
        self.assertIn("1/3 passed", tooltip)

    def test_choose_default_project(self):
        """Test default project selection."""
        project_id, run_id, test_ids = self.create_test_data()

        # Test with no config
        default = self.service.choose_default_project()
        self.assertEqual(default.id, project_id)

        # Test with ID config
        config = {"default_project_id": project_id}
        default = self.service.choose_default_project(config)
        self.assertEqual(default.id, project_id)

        # Test with identifier config
        config = {"default_project_identifier": "test-project"}
        default = self.service.choose_default_project(config)
        self.assertEqual(default.id, project_id)

    def test_project_deletion(self):
        """Test project deletion."""
        project_id, run_id, test_ids = self.create_test_data()

        # Verify project exists
        project = self.service.get_project_by_id(project_id)
        self.assertIsNotNone(project)

        # Delete project
        self.service.delete_project(project_id)

        # Verify project is deleted
        project = self.service.get_project_by_id(project_id)
        self.assertIsNone(project)


if __name__ == '__main__':
    unittest.main()