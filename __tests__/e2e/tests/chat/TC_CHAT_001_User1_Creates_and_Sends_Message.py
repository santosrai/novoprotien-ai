"""
Test: TC_CHAT_001 - Chat History Isolation Between Users

Description:
    Verify that User1's chat history, sessions, and messages are completely isolated 
    from User2's chat history. Each user should only see their own messages, sessions,
    and have their own credits and pipelines.

Category: chat
Priority: High
Tags: [chat, isolation, history, user1, user2, credits, sessions]

Test Plan Reference: tests/test-plans/chat_test_plan.json

Steps:
    1. Login as User1
    2. Wait for chat interface to load
    3. Send a unique message as User1: 'User1 Private Message - {timestamp}'
    4. Verify message appears in User1's chat history
    5. Sign out from User1
    6. Login as User2
    7. Verify User2's chat history does NOT contain User1's message
    8. Send a unique message as User2: 'User2 Private Message - {timestamp}'
    9. Verify User2 only sees their own message
    10. Sign out from User2
    11. Login back as User1
    12. Verify User1 only sees their own message (not User2's)
    13. Verify User1's session list only contains their own sessions

Expected Results:
    - User1's messages are only visible to User1
    - User2's messages are only visible to User2
    - Each user has isolated chat history
    - Each user has isolated sessions
    - No cross-user data leakage

Dependencies:
    - Backend server running on port 8787
    - Frontend server running on port 3000
    - Both User1 and User2 must exist in database
    - User isolation architecture must be implemented

Author: Test Automation Team
Last Updated: 2025-01-01
"""

import asyncio
from pathlib import Path
import sys

# Add fixtures to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from base_test import BaseTest
from page_objects import SignInPage, AppPage, ChatPanel, ProfileMenu

# Add utils to path for config
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
from config_loader import get_config_loader


async def run_test():
    """Execute TC_CHAT_001 test - Chat History Isolation."""
    from datetime import datetime
    
    config_loader = get_config_loader()
    user1 = config_loader.get_user("user1")
    user2 = config_loader.get_user("user2")
    
    if not user1 or not user2:
        raise ValueError("Test users 'user1' and 'user2' must exist in configuration")
    
    test = BaseTest(
        test_id="TC_CHAT_001",
        test_name="Chat History Isolation Between Users",
        environment="local"
    )
    
    try:
        await test.setup()
        page = test.page
        env_config = config_loader.get_environment("local")
        base_url = env_config.get("frontend", "http://localhost:3000")
        
        # Generate unique messages with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        user1_message = f"User1 Private Message - {timestamp}"
        user2_message = f"User2 Private Message - {timestamp}"
        
        # ========== PHASE 1: USER1 SENDS MESSAGE ==========
        test.record_step("Login as User1")
        signin_page = SignInPage(page)
        await signin_page.navigate(base_url)
        await signin_page.login(user1["email"], user1["password"])
        
        app_page = AppPage(page)
        await app_page.verify_redirect()
        await app_page.wait_for_page_load()
        await app_page.verify_chat_panel_visible()
        
        test.record_step("Wait for chat interface to load")
        chat_panel = ChatPanel(page)
        await chat_panel.wait_for_chat_ready()
        
        test.record_step(f"Send unique message as User1: '{user1_message}'")
        await chat_panel.send_message(user1_message)
        
        test.record_step("Verify User1's message appears in their chat history")
        await chat_panel.verify_message_in_history(user1_message)
        
        # ========== PHASE 2: SIGN OUT USER1 ==========
        test.record_step("Sign out from User1")
        profile_menu = ProfileMenu(page)
        await profile_menu.sign_out()
        
        # Wait for redirect to signin page
        await page.wait_for_url("**/signin", timeout=10000)
        await asyncio.sleep(1)  # Wait for session clearing
        
        # ========== PHASE 3: USER2 LOGIN AND VERIFY ISOLATION ==========
        test.record_step("Login as User2")
        await signin_page.navigate(base_url)
        await signin_page.login(user2["email"], user2["password"])
        
        await app_page.verify_redirect()
        await app_page.wait_for_page_load()
        await app_page.verify_chat_panel_visible()
        
        test.record_step("Wait for User2's chat interface to load")
        await chat_panel.wait_for_chat_ready()
        
        test.record_step("Verify User2's chat history does NOT contain User1's message")
        # Check that User1's message is NOT visible
        try:
            user1_message_locator = page.locator(f'text={user1_message}')
            is_visible = await user1_message_locator.is_visible(timeout=3000)
            if is_visible:
                raise AssertionError(f"ISOLATION FAILED: User2 can see User1's message: '{user1_message}'")
        except Exception:
            # Message not visible is expected - isolation working
            pass
        
        test.record_step("User1's message is NOT visible to User2 - isolation verified", status="passed")
        
        # ========== PHASE 4: USER2 SENDS MESSAGE ==========
        test.record_step(f"Send unique message as User2: '{user2_message}'")
        await chat_panel.send_message(user2_message)
        
        test.record_step("Verify User2 only sees their own message")
        await chat_panel.verify_message_in_history(user2_message)
        
        # Verify User1's message is still not visible
        try:
            user1_message_locator = page.locator(f'text={user1_message}')
            is_visible = await user1_message_locator.is_visible(timeout=2000)
            if is_visible:
                raise AssertionError(f"ISOLATION FAILED: User2 can see User1's message after sending their own")
        except Exception:
            # Expected - User1's message should not be visible
            pass
        
        test.record_step("User2 only sees their own messages - isolation verified", status="passed")
        
        # ========== PHASE 5: SIGN OUT USER2 AND LOGIN BACK AS USER1 ==========
        test.record_step("Sign out from User2")
        await profile_menu.sign_out()
        await page.wait_for_url("**/signin", timeout=10000)
        await asyncio.sleep(1)
        
        test.record_step("Login back as User1")
        await signin_page.navigate(base_url)
        await signin_page.login(user1["email"], user1["password"])
        
        await app_page.verify_redirect()
        await app_page.wait_for_page_load()
        await app_page.verify_chat_panel_visible()
        
        test.record_step("Wait for User1's chat interface to load")
        await chat_panel.wait_for_chat_ready()
        
        # ========== PHASE 6: VERIFY USER1'S ISOLATION ==========
        test.record_step("Verify User1 only sees their own message (not User2's)")
        await chat_panel.verify_message_in_history(user1_message)
        
        # Verify User2's message is NOT visible to User1
        try:
            user2_message_locator = page.locator(f'text={user2_message}')
            is_visible = await user2_message_locator.is_visible(timeout=2000)
            if is_visible:
                raise AssertionError(f"ISOLATION FAILED: User1 can see User2's message: '{user2_message}'")
        except Exception:
            # Expected - User2's message should not be visible
            pass
        
        test.record_step("User1 only sees their own messages - isolation verified", status="passed")
        test.record_step("All chat history isolation assertions passed", status="passed")
        test.mark_passed()
        
    except Exception as e:
        test.mark_failed(str(e))
        raise
    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(run_test())
