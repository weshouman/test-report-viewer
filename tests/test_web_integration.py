"""
Integration tests for the web interface.
Tests the Flask adapter and end-to-end web functionality.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_report_viewer.adapters.web.app import create_app
from test_report_viewer.core.models import Project, TestRun, Test, TestResult, Status, create_database


class WebIntegrationTestCase(unittest.TestCase):
    """Integration test cases for web interface."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_fd, self.db_path = tempfile.mkstemp()

        # Create test config
        config = {
            'TESTING': True,
            'projects': [],
            'summary_runs': 10,
            'scan_interval': 10
        }

        # Override database URL for testing
        os.environ['DATABASE_URL'] = f'sqlite:///{self.db_path}'

        # Set up test data first (before creating the app)
        self.setup_test_data()

        # Create app after test data is ready
        self.app = create_app(config)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test method."""
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def setup_test_data(self):
        """Set up test data for integration tests."""
        engine, SessionLocal = create_database(f'sqlite:///{self.db_path}')
        session = SessionLocal()

        try:
            project = Project(
                name="Test Project",
                identifier="test-project",
                out_dir="/tmp/test"
            )
            session.add(project)
            session.commit()

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
            session.add(test_run)
            session.commit()

            # Add some tests
            test1 = Test(project_id=project.id, name="test.example.test_one")
            test2 = Test(project_id=project.id, name="test.example.test_two")
            test3 = Test(project_id=project.id, name="test.example.test_three")
            session.add_all([test1, test2, test3])
            session.commit()

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
            session.add_all([result1, result2, result3])
            session.commit()

            # Store IDs for tests
            self.project_id = project.id
            self.run_id = test_run.id
            self.test_ids = [test1.id, test2.id, test3.id]

        finally:
            session.close()

    def test_index_with_project(self):
        """Test index page redirects to project summary when projects exist."""
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 302)
        self.assertIn(f'/projects/{self.project_id}/summary/', rv.location)

    def test_project_summary(self):
        """Test project summary page displays correctly."""
        rv = self.client.get(f'/projects/{self.project_id}/summary/')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Test Project', rv.data)
        self.assertIn(b'test.example.test_one', rv.data)

    def test_project_summary_404(self):
        """Test project summary returns 404 for non-existent project."""
        rv = self.client.get('/projects/999/summary/')
        self.assertEqual(rv.status_code, 404)

    def test_testrun_view(self):
        """Test test run view page displays correctly."""
        rv = self.client.get(f'/projects/{self.project_id}/runs/{self.run_id}')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Test Project', rv.data)
        self.assertIn(b'passed', rv.data)
        self.assertIn(b'failed', rv.data)
        self.assertIn(b'skipped', rv.data)

    def test_testrun_view_404(self):
        """Test test run view returns 404 for non-existent run."""
        rv = self.client.get(f'/projects/{self.project_id}/runs/999')
        self.assertEqual(rv.status_code, 404)

    def test_test_view(self):
        """Test individual test view page displays correctly."""
        test_id = self.test_ids[0]
        rv = self.client.get(f'/projects/{self.project_id}/tests/{test_id}')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Test Project', rv.data)
        self.assertIn(b'test.example.test_one', rv.data)

    def test_test_view_404(self):
        """Test test view returns 404 for non-existent test."""
        rv = self.client.get(f'/projects/{self.project_id}/tests/999')
        self.assertEqual(rv.status_code, 404)

    def test_api_project_by_identifier(self):
        """Test API endpoint for getting project by identifier."""
        rv = self.client.get('/api/projects/by-identifier/test-project')
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data['identifier'], 'test-project')
        self.assertEqual(data['name'], 'Test Project')

    def test_api_project_by_identifier_404(self):
        """Test API returns 404 for non-existent identifier."""
        rv = self.client.get('/api/projects/by-identifier/non-existent')
        self.assertEqual(rv.status_code, 404)

    def test_project_redirect_by_identifier(self):
        """Test project redirect by identifier."""
        rv = self.client.get('/p/test-project')
        self.assertEqual(rv.status_code, 302)
        self.assertIn(f'/projects/{self.project_id}/summary/', rv.location)

    def test_project_delete(self):
        """Test project deletion."""
        # Verify project exists
        rv = self.client.get(f'/projects/{self.project_id}/summary/')
        self.assertEqual(rv.status_code, 200)

        # Delete project
        rv = self.client.post(f'/projects/{self.project_id}/delete')
        self.assertEqual(rv.status_code, 302)

        # Verify project is deleted
        rv = self.client.get(f'/projects/{self.project_id}/summary/')
        self.assertEqual(rv.status_code, 404)

    def test_summary_with_filters(self):
        """Test project summary with regex filters."""
        # Test include filter
        rv = self.client.get(f'/projects/{self.project_id}/summary/?f_type=include&f_regex=test_one')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'test.example.test_one', rv.data)

        # Test exclude filter
        rv = self.client.get(f'/projects/{self.project_id}/summary/?f_type=exclude&f_regex=test_one')
        self.assertEqual(rv.status_code, 200)
        # Should still show the page but without test_one
        self.assertNotIn(b'test.example.test_one', rv.data)

    def test_summary_subpath(self):
        """Test project summary with subpath navigation."""
        rv = self.client.get(f'/projects/{self.project_id}/summary/test/example')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'test.example.test_one', rv.data)


class WebNoProjectsTestCase(unittest.TestCase):
    """Test cases for web interface when no projects exist."""

    def setUp(self):
        """Set up test fixtures for empty database."""
        self.db_fd, self.db_path = tempfile.mkstemp()

        config = {
            'TESTING': True,
            'projects': []
        }

        # Override database URL for testing
        os.environ['DATABASE_URL'] = f'sqlite:///{self.db_path}'

        # Create empty database
        create_database(f'sqlite:///{self.db_path}')

        self.app = create_app(config)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test method."""
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_index_no_projects(self):
        """Test index page when no projects exist."""
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'No projects configured', rv.data)


if __name__ == '__main__':
    unittest.main()