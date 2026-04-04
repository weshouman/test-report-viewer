"""
Unit tests for the core data models.
Tests model creation, relationships, and basic functionality.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_report_viewer.core.models import Project, TestRun, Test, TestResult, Status, create_database


class ModelsTestCase(unittest.TestCase):
    """Test cases for core data models."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.engine, self.SessionLocal = create_database(f'sqlite:///{self.db_path}')
        self.session = self.SessionLocal()

    def tearDown(self):
        """Clean up after each test method."""
        self.session.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_project_creation(self):
        """Test project model creation and attributes."""
        project = Project(
            name="Test Project",
            identifier="test-project",
            out_dir="/tmp/test"
        )
        self.session.add(project)
        self.session.commit()

        self.assertIsNotNone(project.id)
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(project.identifier, "test-project")
        self.assertEqual(project.out_dir, "/tmp/test")

    def test_status_enum(self):
        """Test Status enum values."""
        self.assertEqual(Status.passed.value, "passed")
        self.assertEqual(Status.failed.value, "failed")
        self.assertEqual(Status.error.value, "error")
        self.assertEqual(Status.skipped.value, "skipped")

    def test_test_result_relationships(self):
        """Test model relationships work correctly."""
        project = Project(name="Test", identifier="test", out_dir="/tmp")
        self.session.add(project)
        self.session.commit()

        test_run = TestRun(project_id=project.id, run_at=datetime.now(), filename="/tmp/test.xml", total=1)
        self.session.add(test_run)
        self.session.commit()

        test = Test(project_id=project.id, name="test.example")
        self.session.add(test)
        self.session.commit()

        result = TestResult(
            test_id=test.id,
            testrun_id=test_run.id,
            status=Status.passed,
            time=0.1
        )
        self.session.add(result)
        self.session.commit()

        # Test relationships
        self.assertEqual(result.test.name, "test.example")
        self.assertEqual(result.testrun.total, 1)
        self.assertEqual(test_run.project.name, "Test")
        self.assertIn(result, test_run.results)

    def test_unique_constraints(self):
        """Test that unique constraints work properly."""
        project = Project(name="Test", identifier="test", out_dir="/tmp")
        self.session.add(project)
        self.session.commit()

        # Test unique project identifier
        duplicate_project = Project(name="Test2", identifier="test", out_dir="/tmp2")
        self.session.add(duplicate_project)

        with self.assertRaises(Exception):  # Should raise IntegrityError
            self.session.commit()

        self.session.rollback()

        # Test unique test name per project
        test1 = Test(project_id=project.id, name="test.example")
        self.session.add(test1)
        self.session.commit()

        test2 = Test(project_id=project.id, name="test.example")
        self.session.add(test2)

        with self.assertRaises(Exception):  # Should raise IntegrityError
            self.session.commit()


if __name__ == '__main__':
    unittest.main()