"""
Basic web integration tests.
Simple tests to verify the web interface loads correctly.
"""

import os
import sys
import tempfile
import unittest

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_report_viewer.adapters.web.app import create_app


class BasicWebTestCase(unittest.TestCase):
    """Basic web interface tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.db_fd, self.db_path = tempfile.mkstemp()

        config = {
            'TESTING': True,
            'projects': []
        }

        # Override database URL for testing
        os.environ['DATABASE_URL'] = f'sqlite:///{self.db_path}'

        self.app = create_app(config)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test method."""
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_app_creation(self):
        """Test that the Flask app can be created."""
        self.assertIsNotNone(self.app)
        self.assertTrue(self.app.config['TESTING'])

    def test_index_no_projects(self):
        """Test index page when no projects exist."""
        rv = self.client.get('/')
        # Should either show "no projects" message or redirect
        self.assertIn(rv.status_code, [200, 302])

    def test_404_handling(self):
        """Test 404 error handling."""
        rv = self.client.get('/nonexistent')
        self.assertEqual(rv.status_code, 404)

    def test_api_nonexistent_project(self):
        """Test API returns 404 for non-existent project."""
        rv = self.client.get('/api/projects/by-identifier/nonexistent')
        self.assertEqual(rv.status_code, 404)


if __name__ == '__main__':
    unittest.main()