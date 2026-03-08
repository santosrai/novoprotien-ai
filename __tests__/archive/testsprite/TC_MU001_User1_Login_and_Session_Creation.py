import asyncio
from playwright import async_api
from playwright.async_api import expect

async def run_test():
    pw = None
    browser = None
    context = None
    
    try:
        # Start a Playwright session in asynchronous mode
        pw = await async_api.async_playwright().start()
        
        # Launch a Chromium browser (headless=False for local testing to see what's happening)
        browser = await pw.chromium.launch(
            headless=False,  # Set to False to see the browser
            args=[
                "--window-size=1280,720",
                "--disable-dev-shm-usage",
            ],
        )
        
        # Create a new browser context (like an incognito window)
        context = await browser.new_context()
        context.set_default_timeout(30000)  # Increased timeout for React rendering
        
        # Open a new page in the browser context
        page = await context.new_page()
        
        # Navigate to /signin page
        print("Navigating to /signin page...")
        await page.goto('http://localhost:3000/signin', wait_until="networkidle", timeout=30000)
        
        # Wait for React to hydrate and form to be ready
        print("Waiting for signin page to load...")
        # Strategy 1: Wait for the signin page test ID
        await page.wait_for_selector('[data-testid="signin-page"]', timeout=30000)
        print("✅ Signin page element found")
        
        # Strategy 2: Wait for the form to be ready
        try:
            await page.wait_for_function(
                '() => document.querySelector("[data-testid=\'signin-page\']")?.getAttribute("data-form-ready") === "true"',
                timeout=10000
            )
            print("✅ Form ready attribute found")
        except async_api.Error:
            try:
                await page.wait_for_function(
                    '() => document.body.getAttribute("data-signin-form-ready") === "true"',
                    timeout=10000
                )
                print("✅ Body form ready attribute found")
            except async_api.Error:
                print("⚠️  Form ready attributes not found, waiting additional time...")
                await asyncio.sleep(2)
        
        # Strategy 3: Wait for the form itself to be visible
        await page.wait_for_selector('[data-testid="signin-form"]', state="visible", timeout=30000)
        print("✅ Signin form is visible")
        
        # Strategy 4: Wait for input fields to be visible and enabled
        await page.wait_for_selector('[data-testid="email-input"]', state="visible", timeout=30000)
        await page.wait_for_selector('[data-testid="password-input"]', state="visible", timeout=30000)
        await page.wait_for_selector('[data-testid="signin-button"]', state="visible", timeout=30000)
        print("✅ All form elements are visible")
        
        # Additional wait to ensure form is fully interactive
        await asyncio.sleep(1)
        
        # Fill in email field
        print("Filling in email: user1@gmail.com")
        email_input = page.locator('[data-testid="email-input"]')
        await email_input.fill('user1@gmail.com')
        await asyncio.sleep(0.5)
        
        # Fill in password field
        print("Filling in password...")
        password_input = page.locator('[data-testid="password-input"]')
        await password_input.fill('test12345')
        await asyncio.sleep(0.5)
        
        # Click sign in button
        print("Clicking sign in button...")
        signin_button = page.locator('[data-testid="signin-button"]')
        await signin_button.click()
        
        # Wait for navigation to /app after successful login
        print("Waiting for navigation to /app...")
        try:
            await page.wait_for_url('**/app', timeout=30000)
            print("✅ Successfully navigated to /app")
        except async_api.Error:
            # Check if we're still on signin page with an error
            current_url = page.url
            if '/signin' in current_url:
                # Check for error message
                try:
                    error_visible = await page.locator('text=/error|failed|invalid/i').first.is_visible(timeout=5000)
                    if error_visible:
                        error_text = await page.locator('text=/error|failed|invalid/i').first.text_content()
                        raise AssertionError(f"Login failed with error: {error_text}")
                except async_api.Error:
                    pass
                raise AssertionError("Login failed: Still on signin page but no error message visible")
            else:
                raise AssertionError(f"Login failed: Unexpected navigation to {current_url}")
        
        # Wait for the app page to load
        print("Waiting for app page to load...")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Verify user is redirected to /app
        current_url = page.url
        if '/app' not in current_url:
            raise AssertionError(f"User was not redirected to /app. Current URL: {current_url}")
        print("✅ Verified navigation to /app")
        
        # Wait for app container to be visible
        await page.wait_for_selector('[data-testid="app-container"]', state="visible", timeout=30000)
        await asyncio.sleep(1)
        print("✅ App container is visible")
        
        # Verify login success by checking multiple indicators:
        verification_passed = False
        verification_errors = []
        
        # Check 1: Verify chat panel is visible (indicates session was created)
        try:
            chat_panel = page.locator('[data-testid="chat-panel"]')
            await expect(chat_panel).to_be_visible(timeout=10000)
            verification_passed = True
            print("✅ Chat panel is visible - session created successfully")
        except AssertionError as e:
            verification_errors.append(f"Chat panel not visible: {str(e)}")
        
        # Check 2: Verify user email or username is displayed in header
        try:
            # ProfileMenu shows username in button, email in dropdown
            user_info = page.locator('text=/user1@gmail.com|User1/i')
            if await user_info.first.is_visible(timeout=5000):
                verification_passed = True
                print("✅ User email/username is displayed in header")
        except AssertionError:
            # Try clicking profile menu to see if email is in dropdown
            try:
                profile_button = page.locator('text=/User1|user1/i').first
                if await profile_button.is_visible(timeout=5000):
                    await profile_button.click()
                    await asyncio.sleep(0.5)
                    email_in_dropdown = page.locator('text=user1@gmail.com')
                    if await email_in_dropdown.is_visible(timeout=5000):
                        verification_passed = True
                        print("✅ User email is displayed in profile menu")
            except Exception as e:
                verification_errors.append(f"Could not verify user email in header: {str(e)}")
        
        # Final verification: If chat panel is visible, login was successful
        if not verification_passed:
            raise AssertionError(
                f"Test case failed: User1 (user1@gmail.com) could not successfully log in and create a chat session as expected. "
                f"Verification errors: {', '.join(verification_errors)}. "
                f"Current URL: {current_url}"
            )
        
        print("✅✅✅ Test passed: User1 successfully logged in and was redirected to /app")
        await asyncio.sleep(3)  # Keep browser open for 3 seconds to see the result
    
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()
            
asyncio.run(run_test())
    