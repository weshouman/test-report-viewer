"""
Meta verification tests for test suite structure and quality.
Validates that test files follow proper patterns and organization.
"""

import ast
import os
import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class MetaTestCase(unittest.TestCase):
    """Meta tests that verify the test suite structure and quality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tests_dir = Path(__file__).parent
        self.expected_test_files = {
            'test_core_models.py': ['ModelsTestCase'],
            'test_core_parser.py': ['ParserTestCase'],
            'test_core_service.py': ['ServiceTestCase'],
            'test_web_basic.py': ['BasicWebTestCase'],
            'test_web_integration.py': ['WebIntegrationTestCase', 'WebNoProjectsTestCase'],
            'test_meta_verification.py': ['MetaTestCase']
        }

    def test_all_expected_test_files_exist(self):
        """Test that all expected test files are present."""
        for test_file in self.expected_test_files.keys():
            file_path = self.tests_dir / test_file
            self.assertTrue(file_path.exists(), f"Test file {test_file} should exist")

    def test_test_file_naming_convention(self):
        """Test that all test files follow naming convention."""
        test_files = list(self.tests_dir.glob("test_*.py"))

        for test_file in test_files:
            # Should start with test_
            self.assertTrue(test_file.name.startswith("test_"),
                           f"Test file {test_file.name} should start with 'test_'")

            # Should end with .py
            self.assertTrue(test_file.name.endswith(".py"),
                           f"Test file {test_file.name} should end with '.py'")

    def test_test_class_structure(self):
        """Test that test files have proper class structure."""
        for test_file, expected_classes in self.expected_test_files.items():
            file_path = self.tests_dir / test_file

            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            try:
                tree = ast.parse(content)
                found_classes = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        found_classes.append(node.name)

                        # Check that test classes inherit from TestCase
                        if node.name.endswith('TestCase'):
                            base_names = []
                            for base in node.bases:
                                if hasattr(base, 'id'):
                                    base_names.append(base.id)
                                elif hasattr(base, 'attr') and hasattr(base, 'value'):
                                    # Handle unittest.TestCase format
                                    if hasattr(base.value, 'id') and base.value.id == 'unittest' and base.attr == 'TestCase':
                                        base_names.append('TestCase')

                            has_testcase = 'TestCase' in base_names or any('TestCase' in name for name in base_names)
                            self.assertTrue(has_testcase,
                                        f"Test class {node.name} in {test_file} should inherit from TestCase")

                # Check expected classes are present
                for expected_class in expected_classes:
                    self.assertIn(expected_class, found_classes,
                                f"Expected class {expected_class} not found in {test_file}")

            except SyntaxError:
                self.fail(f"Syntax error in test file {test_file}")

    def test_test_method_patterns(self):
        """Test that test classes have proper test methods."""
        for test_file in self.expected_test_files.keys():
            file_path = self.tests_dir / test_file

            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.endswith('TestCase'):
                        test_methods = []
                        setup_methods = []
                        teardown_methods = []

                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                if item.name.startswith('test_'):
                                    test_methods.append(item.name)
                                elif item.name == 'setUp':
                                    setup_methods.append(item.name)
                                elif item.name == 'tearDown':
                                    teardown_methods.append(item.name)

                        # Each test class should have at least one test method
                        self.assertGreater(len(test_methods), 0,
                                         f"Test class {node.name} in {test_file} should have at least one test method")

                        # Test methods should follow naming convention
                        for method in test_methods:
                            self.assertTrue(method.startswith('test_'),
                                          f"Test method {method} in {node.name} should start with 'test_'")

                        # If setUp exists, tearDown should probably exist too (warning, not failure)
                        if setup_methods and not teardown_methods and test_file != 'test_meta_verification.py':
                            print(f"[WARNING] {node.name} in {test_file} has setUp but no tearDown")

            except SyntaxError:
                self.fail(f"Syntax error in test file {test_file}")

    def test_required_imports(self):
        """Test that test files have required imports."""
        required_imports = {
            'unittest': ['TestCase', 'main'],
            'os': None,
            'sys': None
        }

        for test_file in self.expected_test_files.keys():
            file_path = self.tests_dir / test_file

            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            # Check for unittest import
            self.assertIn('import unittest', content,
                         f"Test file {test_file} should import unittest")

            # Check for path manipulation (most test files need this)
            if test_file != 'test_meta_verification.py':
                self.assertIn('sys.path.insert', content,
                             f"Test file {test_file} should have sys.path.insert for imports")

    def test_docstring_presence(self):
        """Test that test files and classes have docstrings."""
        for test_file in self.expected_test_files.keys():
            file_path = self.tests_dir / test_file

            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                # Check module docstring
                if ast.get_docstring(tree):
                    module_docstring = ast.get_docstring(tree)
                    self.assertGreater(len(module_docstring.strip()), 10,
                                     f"Module docstring in {test_file} should be descriptive")

                # Check class docstrings
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.endswith('TestCase'):
                        class_docstring = ast.get_docstring(node)
                        self.assertIsNotNone(class_docstring,
                                           f"Test class {node.name} in {test_file} should have a docstring")

            except SyntaxError:
                self.fail(f"Syntax error in test file {test_file}")

    def test_test_organization_stats(self):
        """Test and report test organization statistics."""
        total_test_files = 0
        total_test_classes = 0
        total_test_methods = 0

        for test_file in self.tests_dir.glob("test_*.py"):
            total_test_files += 1

            with open(test_file, 'r') as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.endswith('TestCase'):
                        total_test_classes += 1

                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                                total_test_methods += 1

            except SyntaxError:
                continue

        # Calculate expected minimums based on our defined structure
        expected_test_files_count = len(self.expected_test_files)
        expected_test_classes_count = sum(len(classes) for classes in self.expected_test_files.values())
        minimum_methods_per_class = 2  # Reasonable minimum: each test class should have at least 2 test methods
        expected_minimum_methods = expected_test_classes_count * minimum_methods_per_class

        # Print statistics (visible in verbose test output)
        print(f"\n[TEST STATS] Files: {total_test_files}/{expected_test_files_count}, "
              f"Classes: {total_test_classes}/{expected_test_classes_count}, "
              f"Methods: {total_test_methods} (min: {expected_minimum_methods})")

        # Assert dynamic minimums based on expected structure
        self.assertEqual(total_test_files, expected_test_files_count,
                        f"Should have exactly {expected_test_files_count} test files as defined in expected_test_files")

        self.assertEqual(total_test_classes, expected_test_classes_count,
                        f"Should have exactly {expected_test_classes_count} test classes as defined in expected_test_files")

        self.assertGreaterEqual(total_test_methods, expected_minimum_methods,
                               f"Should have at least {minimum_methods_per_class} test methods per class "
                               f"({expected_test_classes_count} classes × {minimum_methods_per_class} = {expected_minimum_methods} minimum)")

    def test_no_duplicate_test_methods(self):
        """Test that there are no duplicate test method names within classes."""
        for test_file in self.expected_test_files.keys():
            file_path = self.tests_dir / test_file

            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.endswith('TestCase'):
                        method_names = []

                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                method_names.append(item.name)

                        # Check for duplicates
                        duplicates = [name for name in set(method_names) if method_names.count(name) > 1]
                        self.assertEqual(len(duplicates), 0,
                                       f"Duplicate methods found in {node.name} of {test_file}: {duplicates}")

            except SyntaxError:
                self.fail(f"Syntax error in test file {test_file}")


if __name__ == '__main__':
    # Run with verbose output to see statistics
    unittest.main(verbosity=2)