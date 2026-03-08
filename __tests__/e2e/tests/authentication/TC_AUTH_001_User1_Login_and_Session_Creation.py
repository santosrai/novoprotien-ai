"""
Test: TC_AUTH_001 - User1 Login and Session Creation

Description:
    Verify User1 (user1@gmail.com / test12345) can successfully log in 
    and create a chat session.

Category: authentication
Priority: High
Tags: [login, session, user1]

Test Plan Reference: tests/test-plans/authentication_test_plan.json

Steps:
    1. Navigate to /signin page
    2. Enter email: user1@gmail.com
    3. Enter password: test12345
    4. Click Sign in button
    5. Verify redirect to /app
    6. Verify chat session is created
    7. Verify user email is displayed

Expected Results:
    - User is redirected to /app
    - Chat panel is visible
    - User email is displayed in header

Dependencies:
    - Backend server running on port 8787
    - Frontend server running on port 3000
    - Test user exists in database

Author: Test Automation Team
Last Updated: 2025-01-01
"""

import asyncio
from pathlib import Path
import sys

# Add fixtures to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from base_test import BaseTest
from page_objects import SignInPage, AppPage

# Add utils to path for config
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
from config_loader import get_config_loader


async def run_test():
    """Execute TC_AUTH_001 test."""
    config_loader = get_config_loader()
    user = config_loader.get_user("user1")
    
    if not user:
        raise ValueError("Test user 'user1' not found in configuration")
    
    test = BaseTest(
        test_id="TC_AUTH_001",
        test_name="User1 Login and Session Creation",
        environment="local"
    )
    
    try:
        await test.setup()
        page = test.page
        env_config = config_loader.get_environment("local")
        base_url = env_config.get("frontend", "http://localhost:3000")
        
        # Step 1: Navigate to signin page
        test.record_step("Navigate to /signin page")
        signin_page = SignInPage(page)
        await signin_page.navigate(base_url)
        
        # Step 2-4: Login
        test.record_step(f"Enter email: {user['email']}")
        test.record_step("Enter password")
        test.record_step("Click Sign in button")
        await signin_page.login(user["email"], user["password"])
        
        # Step 5-7: Verify login success
        test.record_step("Verify redirect to /app")
        app_page = AppPage(page)
        await app_page.verify_redirect()
        await app_page.wait_for_page_load()
        
        test.record_step("Verify chat panel is visible")
        await app_page.verify_chat_panel_visible()
        
        test.record_step("Verify user email is displayed")
        await app_page.verify_user_email_displayed(user["email"])
        
        test.record_step("All assertions passed", status="passed")
        test.mark_passed()
        
    except Exception as e:
        test.mark_failed(str(e))
        raise
    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(run_test())
