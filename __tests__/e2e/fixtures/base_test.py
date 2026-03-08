"""
Base test class providing common test infrastructure.
All tests should inherit from or use this class.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import sys

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from config_loader import get_config_loader


class BaseTest:
    """Base test class with common setup and teardown."""
    
    def __init__(
        self,
        test_id: str,
        test_name: str,
        environment: str = "local"
    ):
        """Initialize base test.
        
        Args:
            test_id: Test case ID (e.g., 'TC_AUTH_001')
            test_name: Test case name
            environment: Environment name (default: 'local')
        """
        self.test_id = test_id
        self.test_name = test_name
        self.environment = environment
        
        # Config loader
        self.config_loader = get_config_loader()
        self.config_loader.set_environment(environment)
        self.config = self.config_loader.load_config()
        self.test_settings = self.config_loader.get_test_settings()
        self.wait_strategies = self.config_loader.get_wait_strategies()
        self.env_config = self.config_loader.get_environment(environment)
        
        # Playwright objects
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Test tracking
        self.status: str = "pending"
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.steps: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.screenshot_path: Optional[str] = None
        
        # Reports directory
        # Get tests directory (parent of fixtures)
        tests_dir = Path(__file__).parent.parent
        self.reports_dir = tests_dir / "reports" / "latest"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.reports_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    async def setup(self):
        """Set up browser and page for test execution."""
        self.start_time = datetime.now()
        self.status = "running"
        
        # Start Playwright
        self.playwright = await async_playwright().start()
        
        # Get browser type
        browser_type = getattr(self.playwright, self.test_settings.get("browser", "chromium"))
        
        # Launch browser
        browser_args = [
            f"--window-size={self.test_settings['viewport']['width']},{self.test_settings['viewport']['height']}",
            "--disable-dev-shm-usage",
        ]
        
        self.browser = await browser_type.launch(
            headless=self.test_settings.get("headless", False),
            args=browser_args
        )
        
        # Create context
        viewport = self.test_settings.get("viewport", {"width": 1280, "height": 720})
        self.context = await self.browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]}
        )
        self.context.set_default_timeout(self.test_settings.get("defaultTimeout", 30000))
        
        # Create page
        self.page = await self.context.new_page()
        
        self.record_step("Browser and page setup completed", status="passed")
    
    async def teardown(self):
        """Clean up browser and page after test execution."""
        self.end_time = datetime.now()
        
        # Take screenshot on failure
        if self.status == "failed" and self.test_settings.get("screenshotOnFailure", True):
            try:
                if self.page:
                    screenshot_file = self.screenshots_dir / f"{self.test_id}.png"
                    await self.page.screenshot(path=str(screenshot_file), full_page=True)
                    self.screenshot_path = str(screenshot_file)
            except Exception as e:
                print(f"Failed to take screenshot: {e}")
        
        # Close browser
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        self.record_step("Browser and page teardown completed", status="passed")
    
    def record_step(self, description: str, status: str = "passed", duration: Optional[float] = None):
        """Record a test step.
        
        Args:
            description: Step description
            status: Step status ('passed', 'failed', 'skipped')
            duration: Step duration in seconds
        """
        step = {
            "step": len(self.steps) + 1,
            "description": description,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        if duration is not None:
            step["duration"] = duration
        
        self.steps.append(step)
    
    def mark_passed(self):
        """Mark test as passed."""
        self.status = "passed"
        if self.end_time is None:
            self.end_time = datetime.now()
    
    def mark_failed(self, error: str):
        """Mark test as failed.
        
        Args:
            error: Error message
        """
        self.status = "failed"
        self.error = error
        if self.end_time is None:
            self.end_time = datetime.now()
        self.record_step(f"Test failed: {error}", status="failed")
    
    def mark_skipped(self, reason: str = ""):
        """Mark test as skipped.
        
        Args:
            reason: Skip reason
        """
        self.status = "skipped"
        if self.end_time is None:
            self.end_time = datetime.now()
        self.record_step(f"Test skipped: {reason}", status="skipped")
    
    def get_duration(self) -> float:
        """Get test duration in seconds.
        
        Returns:
            Duration in seconds
        """
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary.
        
        Returns:
            Test result dictionary
        """
        return {
            "id": self.test_id,
            "name": self.test_name,
            "status": self.status,
            "duration": self.get_duration(),
            "startTime": self.start_time.isoformat() if self.start_time else None,
            "endTime": self.end_time.isoformat() if self.end_time else None,
            "steps": self.steps,
            "error": self.error,
            "screenshot": self.screenshot_path,
            "environment": self.environment,
        }
    
    async def wait_for_react(self):
        """Wait for React to render (if wait strategy is enabled)."""
        if not self.wait_strategies.get("waitForReact", False):
            return
        
        if not self.page:
            return
        
        timeout = self.wait_strategies.get("reactTimeout", 5000)
        try:
            # Wait for React to be ready
            await self.page.wait_for_function(
                '() => window.React !== undefined || document.querySelector("[data-testid]") !== null',
                timeout=timeout
            )
            await asyncio.sleep(0.5)  # Small delay for React to finish rendering
        except Exception:
            # React might not be available, continue anyway
            pass
    
    async def navigate_and_wait(self, url: str, wait_for_network_idle: bool = True):
        """Navigate to URL and wait for page to be ready.
        
        Args:
            url: URL to navigate to
            wait_for_network_idle: Whether to wait for network idle
        """
        if not self.page:
            raise RuntimeError("Page not initialized. Call setup() first.")
        
        timeout = self.test_settings.get("navigationTimeout", 30000)
        
        if wait_for_network_idle and self.wait_strategies.get("networkIdle", True):
            await self.page.goto(url, wait_until="networkidle", timeout=timeout)
        else:
            await self.page.goto(url, wait_until="load", timeout=timeout)
        
        # Wait for React if enabled
        await self.wait_for_react()
        
        self.record_step(f"Navigated to {url}")
