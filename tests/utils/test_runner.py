"""
Test runner for executing Playwright tests.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from config_loader import get_config_loader
from test_discovery import TestDiscovery
from report_generator import ReportGenerator


class TestRunner:
    """Execute tests and generate reports."""
    
    def __init__(self, environment: str = "local"):
        """Initialize test runner.
        
        Args:
            environment: Environment name (default: 'local')
        """
        self.environment = environment
        self.config_loader = get_config_loader()
        self.config_loader.set_environment(environment)
        self.test_discovery = TestDiscovery()
        self.report_generator = ReportGenerator()
        self.test_results: List[Dict[str, Any]] = []
    
    def discover_tests(
        self,
        category: Optional[str] = None,
        test_ids: Optional[List[str]] = None,
        pattern: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Discover tests to run.
        
        Args:
            category: Test category to filter by
            test_ids: List of specific test IDs to run
            pattern: Regex pattern to match test IDs or names
            
        Returns:
            List of test dictionaries
        """
        if test_ids:
            # Get specific tests by ID
            tests = []
            for test_id in test_ids:
                test = self.test_discovery.get_test_by_id(test_id)
                if test:
                    tests.append(test)
            return tests
        
        # Discover tests by category or pattern
        return self.test_discovery.discover_tests(category=category, pattern=pattern)
    
    async def run_test(self, test_info: Dict[str, str]) -> Dict[str, Any]:
        """Run a single test.
        
        Args:
            test_info: Test information dictionary
            
        Returns:
            Test result dictionary
        """
        test_file = Path(test_info['file'])
        
        # Load test module
        spec = importlib.util.spec_from_file_location("test_module", test_file)
        if spec is None or spec.loader is None:
            return {
                'id': test_info['id'],
                'name': test_info['name'],
                'file': str(test_file),
                'category': test_info['category'],
                'status': 'failed',
                'duration': 0,
                'error': f"Failed to load test module: {test_file}",
                'steps': [],
                'environment': self.environment,
            }
        
        module = importlib.util.module_from_spec(spec)
        sys.modules['test_module'] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            return {
                'id': test_info['id'],
                'name': test_info['name'],
                'file': str(test_file),
                'category': test_info['category'],
                'status': 'failed',
                'duration': 0,
                'error': f"Failed to import test module: {str(e)}",
                'steps': [],
                'environment': self.environment,
            }
        
        # Execute test
        if hasattr(module, 'run_test'):
            try:
                await module.run_test()
                
                # Get result from BaseTest if available
                # Note: This requires the test to expose its result
                # For now, we'll assume the test handles its own reporting
                return {
                    'id': test_info['id'],
                    'name': test_info['name'],
                    'file': str(test_file),
                    'category': test_info['category'],
                    'status': 'passed',  # Will be updated by test itself
                    'duration': 0,
                    'steps': [],
                    'environment': self.environment,
                }
            except Exception as e:
                return {
                    'id': test_info['id'],
                    'name': test_info['name'],
                    'file': str(test_file),
                    'category': test_info['category'],
                    'status': 'failed',
                    'duration': 0,
                    'error': str(e),
                    'steps': [],
                    'environment': self.environment,
                }
        else:
            return {
                'id': test_info['id'],
                'name': test_info['name'],
                'file': str(test_file),
                'category': test_info['category'],
                'status': 'failed',
                'duration': 0,
                'error': "Test module does not have 'run_test' function",
                'steps': [],
                'environment': self.environment,
            }
    
    async def run_tests(
        self,
        category: Optional[str] = None,
        test_ids: Optional[List[str]] = None,
        pattern: Optional[str] = None,
        parallel: bool = False
    ) -> Dict[str, Any]:
        """Run tests and generate reports.
        
        Args:
            category: Test category to filter by
            test_ids: List of specific test IDs to run
            pattern: Regex pattern to match test IDs or names
            parallel: Whether to run tests in parallel
            
        Returns:
            Test execution summary
        """
        # Discover tests
        tests = self.discover_tests(category=category, test_ids=test_ids, pattern=pattern)
        
        if not tests:
            print("No tests found to run.")
            return {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
            }
        
        print(f"Found {len(tests)} test(s) to run")
        print("-" * 60)
        
        # Run tests
        if parallel:
            # Run tests in parallel
            tasks = [self.run_test(test) for test in tests]
            self.test_results = await asyncio.gather(*tasks)
        else:
            # Run tests sequentially
            self.test_results = []
            for i, test in enumerate(tests, 1):
                print(f"\n[{i}/{len(tests)}] Running {test['id']} - {test['name']}")
                result = await self.run_test(test)
                self.test_results.append(result)
                
                status_icon = "✅" if result.get('status') == 'passed' else "❌"
                print(f"{status_icon} {result['id']}: {result.get('status', 'unknown')}")
                if result.get('error'):
                    print(f"   Error: {result['error']}")
        
        # Generate reports
        test_run_id = f"run-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        json_report = self.report_generator.generate_json_report(self.test_results, test_run_id)
        md_report = self.report_generator.generate_markdown_report(self.test_results, test_run_id)
        
        print("\n" + "=" * 60)
        print("Test Execution Summary")
        print("=" * 60)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.get('status') == 'passed')
        failed = sum(1 for r in self.test_results if r.get('status') == 'failed')
        skipped = sum(1 for r in self.test_results if r.get('status') == 'skipped')
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Total: {total}")
        print(f"Passed: {passed} ({pass_rate:.2f}%)")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        print(f"\nReports generated:")
        print(f"  - JSON: {json_report}")
        print(f"  - Markdown: {md_report}")
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'passRate': pass_rate,
            'jsonReport': str(json_report),
            'markdownReport': str(md_report),
        }


async def main():
    """Main entry point for test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Playwright tests')
    parser.add_argument('--category', '-c', help='Test category to run')
    parser.add_argument('--test-id', '-t', action='append', help='Specific test ID to run (can be used multiple times)')
    parser.add_argument('--pattern', '-p', help='Regex pattern to match test IDs or names')
    parser.add_argument('--environment', '-e', default='local', help='Environment name (default: local)')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    
    args = parser.parse_args()
    
    runner = TestRunner(environment=args.environment)
    await runner.run_tests(
        category=args.category,
        test_ids=args.test_id,
        pattern=args.pattern,
        parallel=args.parallel
    )


if __name__ == "__main__":
    asyncio.run(main())
