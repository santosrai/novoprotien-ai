"""
Test discovery utility to find and categorize tests.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional


class TestDiscovery:
    """Discover and categorize test files."""
    
    def __init__(self, tests_dir: Optional[Path] = None):
        """Initialize test discovery.
        
        Args:
            tests_dir: Directory containing tests. Defaults to tests/tests/
        """
        if tests_dir is None:
            tests_dir = Path(__file__).parent.parent / "tests"
        self.tests_dir = Path(tests_dir)
    
    def discover_tests(self, category: Optional[str] = None, pattern: Optional[str] = None) -> List[Dict[str, str]]:
        """Discover test files.
        
        Args:
            category: Test category to filter by (e.g., 'authentication')
            pattern: Regex pattern to match test IDs or names
            
        Returns:
            List of test dictionaries with id, name, file, and category
        """
        tests = []
        
        # Search in category subdirectories
        if category:
            category_dir = self.tests_dir / category
            if category_dir.exists():
                tests.extend(self._discover_in_directory(category_dir, category))
        else:
            # Search all categories
            for category_dir in self.tests_dir.iterdir():
                if category_dir.is_dir() and not category_dir.name.startswith('_'):
                    tests.extend(self._discover_in_directory(category_dir, category_dir.name))
        
        # Filter by pattern if provided
        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            tests = [
                t for t in tests
                if regex.search(t['id']) or regex.search(t['name']) or regex.search(t['file'])
            ]
        
        return sorted(tests, key=lambda x: x['id'])
    
    def _discover_in_directory(self, directory: Path, category: str) -> List[Dict[str, str]]:
        """Discover tests in a specific directory.
        
        Args:
            directory: Directory to search
            category: Category name
            
        Returns:
            List of test dictionaries
        """
        tests = []
        
        for test_file in directory.glob("TC_*.py"):
            test_info = self._parse_test_file(test_file, category)
            if test_info:
                tests.append(test_info)
        
        return tests
    
    def _parse_test_file(self, test_file: Path, category: str) -> Optional[Dict[str, str]]:
        """Parse test file to extract test information.
        
        Args:
            test_file: Path to test file
            category: Category name
            
        Returns:
            Test dictionary or None if parsing fails
        """
        # Extract test ID from filename (TC_CATEGORY_ID_Description.py)
        filename = test_file.stem
        match = re.match(r'TC_([A-Z]+)_(\d+)_(.+)', filename)
        if not match:
            return None
        
        category_prefix, test_num, description = match.groups()
        test_id = f"TC_{category_prefix}_{test_num}"
        
        # Try to extract name from docstring
        test_name = description.replace('_', ' ')
        
        try:
            with open(test_file, 'r') as f:
                content = f.read()
                # Look for test name in docstring
                name_match = re.search(r'Test:\s*([^\n]+)', content)
                if name_match:
                    test_name = name_match.group(1).strip()
        except Exception:
            pass
        
        return {
            'id': test_id,
            'name': test_name,
            'file': str(test_file),
            'category': category,
        }
    
    def get_test_by_id(self, test_id: str) -> Optional[Dict[str, str]]:
        """Get test by ID.
        
        Args:
            test_id: Test case ID (e.g., 'TC_AUTH_001')
            
        Returns:
            Test dictionary or None if not found
        """
        tests = self.discover_tests()
        for test in tests:
            if test['id'] == test_id:
                return test
        return None
