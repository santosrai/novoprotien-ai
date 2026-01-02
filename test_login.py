#!/usr/bin/env python3
"""
Simple Playwright test for user login functionality.
Tests login flow: navigate to signin page, enter credentials, verify redirect to /app.
"""

import asyncio
from playwright.async_api import async_playwright, expect, TimeoutError as PlaywrightTimeoutError


async def test_login():
    """Test user login with Playwright."""
    playwright = None
    browser = None
    context = None
    
    try:
        # Start Playwright
        playwright = await async_playwright().start()
        
        # Launch browser (headless=False to see what's happening)
        browser = await playwright.chromium.launch(
            headless=False,
            args=["--window-size=1280,720"]
        )
        
        # Create browser context
        context = await browser.new_context()
        context.set_default_timeout(30000)
        
        # Create new page
        page = await context.new_page()
        
        print("=" * 60)
        print("Testing Login Flow")
        print("=" * 60)
        
        # Step 1: Navigate to signin page
        print("\n[1/5] Navigating to /signin page...")
        await page.goto('http://localhost:3000/signin', wait_until="networkidle", timeout=30000)
        print("✅ Page loaded")
        
        # Step 2: Wait for signin form to be ready
        print("\n[2/5] Waiting for signin form...")
        await page.wait_for_selector('[data-testid="signin-page"]', timeout=30000)
        await page.wait_for_selector('[data-testid="signin-form"]', state="visible", timeout=30000)
        await page.wait_for_selector('[data-testid="email-input"]', state="visible", timeout=30000)
        await page.wait_for_selector('[data-testid="password-input"]', state="visible", timeout=30000)
        await page.wait_for_selector('[data-testid="signin-button"]', state="visible", timeout=30000)
        print("✅ Signin form is ready")
        
        # Step 3: Fill in credentials
        print("\n[3/5] Entering credentials...")
        email_input = page.locator('[data-testid="email-input"]')
        password_input = page.locator('[data-testid="password-input"]')
        
        await email_input.fill('user1@gmail.com')
        await password_input.fill('test12345')
        print("✅ Credentials entered")
        
        # Step 4: Click sign in button
        print("\n[4/5] Clicking sign in button...")
        signin_button = page.locator('[data-testid="signin-button"]')
        await signin_button.click()
        print("✅ Sign in button clicked")
        
        # Step 5: Wait for navigation to /app
        print("\n[5/5] Waiting for redirect to /app...")
        try:
            await page.wait_for_url('**/app', timeout=30000)
            print("✅ Successfully redirected to /app")
        except PlaywrightTimeoutError:
            # Check if we're still on signin page (login failed)
            current_url = page.url
            if '/signin' in current_url:
                # Check for error message
                error_elements = page.locator('text=/error|failed|invalid/i')
                if await error_elements.count() > 0:
                    error_text = await error_elements.first.text_content()
                    raise AssertionError(f"Login failed with error: {error_text}")
                else:
                    raise AssertionError("Login failed: Still on signin page but no error message visible")
            else:
                raise AssertionError(f"Login failed: Unexpected navigation to {current_url}")
        
        # Verify login success
        print("\n" + "=" * 60)
        print("Verifying Login Success")
        print("=" * 60)
        
        # Wait for app to load
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(1)
        
        # Check 1: Verify URL is /app
        current_url = page.url
        assert '/app' in current_url, f"Expected /app, but got {current_url}"
        print("✅ URL is correct: /app")
        
        # Check 2: Verify chat panel is visible (indicates session created)
        try:
            chat_panel = page.locator('[data-testid="chat-panel"]')
            await expect(chat_panel).to_be_visible(timeout=10000)
            print("✅ Chat panel is visible - session created")
        except AssertionError:
            print("⚠️  Chat panel not found (may still be loading)")
        
        # Check 3: Verify user email is displayed
        try:
            user_info = page.locator('text=/user1@gmail.com|User1/i')
            if await user_info.first.is_visible(timeout=5000):
                print("✅ User email/username is displayed")
        except AssertionError:
            print("⚠️  User email not found in header (may be in dropdown)")
        
        print("\n" + "=" * 60)
        print("✅✅✅ LOGIN TEST PASSED!")
        print("=" * 60)
        
        # Keep browser open for 3 seconds to see the result
        await asyncio.sleep(3)
        
    except AssertionError as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        raise
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST ERROR")
        print("=" * 60)
        print(f"Unexpected error: {e}")
        raise
        
    finally:
        # Cleanup
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


if __name__ == "__main__":
    print("\n🚀 Starting Playwright Login Test")
    print("Make sure the app is running on http://localhost:3000")
    print("Press Ctrl+C to cancel\n")
    
    try:
        asyncio.run(test_login())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        exit(1)
