"""
Generate test reports in JSON and Markdown formats.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class ReportGenerator:
    """Generate test execution reports."""
    
    def __init__(self, reports_dir: Optional[Path] = None):
        """Initialize report generator.
        
        Args:
            reports_dir: Directory for reports. Defaults to tests/reports/latest/
        """
        if reports_dir is None:
            reports_dir = Path(__file__).parent.parent.parent / "tests" / "reports" / "latest"
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_json_report(self, test_results: List[Dict[str, Any]], test_run_id: Optional[str] = None) -> Path:
        """Generate JSON test report.
        
        Args:
            test_results: List of test result dictionaries
            test_run_id: Optional test run ID
            
        Returns:
            Path to generated JSON report
        """
        if test_run_id is None:
            test_run_id = f"run-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        
        # Calculate summary
        total = len(test_results)
        passed = sum(1 for t in test_results if t.get('status') == 'passed')
        failed = sum(1 for t in test_results if t.get('status') == 'failed')
        skipped = sum(1 for t in test_results if t.get('status') == 'skipped')
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # Calculate total duration
        total_duration = sum(t.get('duration', 0) for t in test_results)
        
        report = {
            "testRun": {
                "id": test_run_id,
                "timestamp": datetime.now().isoformat(),
                "duration": total_duration,
                "environment": test_results[0].get('environment', 'local') if test_results else 'local'
            },
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "passRate": round(pass_rate, 2)
            },
            "tests": test_results
        }
        
        # Write JSON report
        json_file = self.reports_dir / "test_results.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return json_file
    
    def generate_markdown_report(self, test_results: List[Dict[str, Any]], test_run_id: Optional[str] = None) -> Path:
        """Generate Markdown test report.
        
        Args:
            test_results: List of test result dictionaries
            test_run_id: Optional test run ID
            
        Returns:
            Path to generated Markdown report
        """
        if test_run_id is None:
            test_run_id = f"run-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        
        # Calculate summary
        total = len(test_results)
        passed = sum(1 for t in test_results if t.get('status') == 'passed')
        failed = sum(1 for t in test_results if t.get('status') == 'failed')
        skipped = sum(1 for t in test_results if t.get('status') == 'skipped')
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # Generate markdown
        md_lines = [
            "# Test Execution Report",
            "",
            "---",
            "",
            "## 1️⃣ Document Metadata",
            f"- **Project Name:** novoprotien-ai",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d')}",
            f"- **Test Run ID:** {test_run_id}",
            f"- **Prepared by:** Test Automation Framework",
            f"- **Test Type:** Frontend End-to-End Testing",
            "",
            "---",
            "",
            "## 2️⃣ Executive Summary",
            "",
            f"**Overall Results:**",
            f"- **Total Tests:** {total}",
            f"- **Passed:** {passed} ({pass_rate:.2f}%)",
            f"- **Failed:** {failed} ({100-pass_rate:.2f}%)",
            f"- **Skipped:** {skipped}",
            "",
            "---",
            "",
            "## 3️⃣ Test Results Summary",
            "",
            "| Test ID | Test Name | Status | Duration (s) | Error |",
            "|---------|-----------|--------|-------------|-------|",
        ]
        
        # Add test rows
        for test in test_results:
            status_icon = "✅" if test.get('status') == 'passed' else "❌" if test.get('status') == 'failed' else "⏭️"
            duration = test.get('duration', 0)
            error = test.get('error', '')
            if error:
                error = error[:50] + "..." if len(error) > 50 else error
            
            md_lines.append(
                f"| {test.get('id', 'N/A')} | {test.get('name', 'N/A')} | {status_icon} {test.get('status', 'unknown')} | {duration:.2f} | {error} |"
            )
        
        md_lines.extend([
            "",
            "---",
            "",
            "## 4️⃣ Detailed Test Results",
            "",
        ])
        
        # Add detailed results for each test
        for test in test_results:
            status_icon = "✅" if test.get('status') == 'passed' else "❌" if test.get('status') == 'failed' else "⏭️"
            
            md_lines.extend([
                f"### {test.get('id', 'N/A')} - {test.get('name', 'N/A')}",
                "",
                f"- **Status:** {status_icon} {test.get('status', 'unknown')}",
                f"- **Duration:** {test.get('duration', 0):.2f} seconds",
                f"- **File:** `{test.get('file', 'N/A')}`",
                "",
            ])
            
            # Add steps
            steps = test.get('steps', [])
            if steps:
                md_lines.append("**Steps:**")
                md_lines.append("")
                for step in steps:
                    step_status = step.get('status', 'unknown')
                    step_icon = "✅" if step_status == 'passed' else "❌" if step_status == 'failed' else "⏭️"
                    md_lines.append(f"- {step_icon} Step {step.get('step', '?')}: {step.get('description', 'N/A')}")
                md_lines.append("")
            
            # Add error if failed
            if test.get('status') == 'failed' and test.get('error'):
                md_lines.extend([
                    "**Error:**",
                    "",
                    f"```",
                    test.get('error', ''),
                    "```",
                    "",
                ])
            
            # Add screenshot if available
            if test.get('screenshot'):
                md_lines.extend([
                    f"**Screenshot:** `{test.get('screenshot')}`",
                    "",
                ])
            
            md_lines.append("---")
            md_lines.append("")
        
        # Add recommendations
        if failed > 0:
            md_lines.extend([
                "## 5️⃣ Recommendations",
                "",
                f"- {failed} test(s) failed. Review error messages and screenshots above.",
                "- Check application logs for additional context.",
                "- Verify test data is correct.",
                "",
            ])
        
        # Write markdown report
        md_file = self.reports_dir / "test_report.md"
        with open(md_file, 'w') as f:
            f.write('\n'.join(md_lines))
        
        return md_file
