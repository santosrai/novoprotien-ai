"""
Helper functions for test utilities.
"""

import asyncio
from typing import Optional
from playwright.async_api import Page


async def wait_for_react_ready(page: Page, timeout: int = 5000):
    """Wait for React to be ready.
    
    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds
    """
    try:
        await page.wait_for_function(
            '() => window.React !== undefined || document.querySelector("[data-testid]") !== null',
            timeout=timeout
        )
        await asyncio.sleep(0.5)
    except Exception:
        # React might not be available, continue anyway
        pass


async def wait_for_element_visible(page: Page, selector: str, timeout: int = 30000):
    """Wait for element to be visible.
    
    Args:
        page: Playwright page object
        selector: CSS selector
        timeout: Timeout in milliseconds
    """
    await page.wait_for_selector(selector, state="visible", timeout=timeout)


async def take_screenshot_on_failure(page: Page, test_id: str, screenshots_dir: str):
    """Take screenshot on test failure.
    
    Args:
        page: Playwright page object
        test_id: Test case ID
        screenshots_dir: Directory to save screenshot
    """
    from pathlib import Path
    screenshot_path = Path(screenshots_dir) / f"{test_id}.png"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    return str(screenshot_path)
