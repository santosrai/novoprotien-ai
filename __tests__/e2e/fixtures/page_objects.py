"""
Page Object Model classes for reusable page interactions.
"""

import asyncio
import re
from typing import Optional
from playwright.async_api import Page, expect, TimeoutError as PlaywrightTimeoutError


class SignInPage:
    """Page object for the sign-in page."""
    
    def __init__(self, page: Page):
        """Initialize sign-in page object.
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    async def navigate(self, base_url: Optional[str] = None):
        """Navigate to sign-in page.
        
        Args:
            base_url: Base URL (defaults to localhost:3000)
        """
        if base_url is None:
            base_url = "http://localhost:3000"
        
        url = f"{base_url}/signin"
        await self.page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Wait for React to render
        await asyncio.sleep(1)
        
        # Wait for signin page to be ready
        await self.page.wait_for_selector('[data-testid="signin-page"]', timeout=30000)
        await self.page.wait_for_selector('[data-testid="signin-form"]', state="visible", timeout=30000)
    
    async def wait_for_form_ready(self, timeout: int = 30000):
        """Wait for sign-in form to be ready.
        
        Args:
            timeout: Timeout in milliseconds
        """
        # Wait for form ready attribute
        try:
            await self.page.wait_for_function(
                '() => document.querySelector("[data-testid=\'signin-page\']")?.getAttribute("data-form-ready") === "true"',
                timeout=10000
            )
        except PlaywrightTimeoutError:
            try:
                await self.page.wait_for_function(
                    '() => document.body.getAttribute("data-signin-form-ready") === "true"',
                    timeout=10000
                )
            except PlaywrightTimeoutError:
                # Form ready attributes not found, wait additional time
                await asyncio.sleep(2)
        
        # Wait for input fields
        await self.page.wait_for_selector('[data-testid="email-input"]', state="visible", timeout=timeout)
        await self.page.wait_for_selector('[data-testid="password-input"]', state="visible", timeout=timeout)
        await self.page.wait_for_selector('[data-testid="signin-button"]', state="visible", timeout=timeout)
    
    async def fill_email(self, email: str):
        """Fill email input field.
        
        Args:
            email: Email address
        """
        email_input = self.page.locator('[data-testid="email-input"]')
        await email_input.fill(email)
        await asyncio.sleep(0.5)
    
    async def fill_password(self, password: str):
        """Fill password input field.
        
        Args:
            password: Password
        """
        password_input = self.page.locator('[data-testid="password-input"]')
        await password_input.fill(password)
        await asyncio.sleep(0.5)
    
    async def click_signin_button(self):
        """Click the sign-in button."""
        signin_button = self.page.locator('[data-testid="signin-button"]')
        await signin_button.click()
    
    async def login(self, email: str, password: str):
        """Perform complete login flow.
        
        Args:
            email: Email address
            password: Password
        """
        await self.wait_for_form_ready()
        await self.fill_email(email)
        await self.fill_password(password)
        await self.click_signin_button()
    
    async def get_error_message(self) -> Optional[str]:
        """Get error message if login failed.
        
        Returns:
            Error message or None
        """
        try:
            error_element = self.page.locator('text=/error|failed|invalid/i').first
            if await error_element.is_visible(timeout=5000):
                return await error_element.text_content()
        except PlaywrightTimeoutError:
            pass
        return None


class AppPage:
    """Page object for the main app page."""
    
    def __init__(self, page: Page):
        """Initialize app page object.
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    async def verify_redirect(self, expected_path: str = "/app", timeout: int = 30000):
        """Verify redirect to app page.
        
        Args:
            expected_path: Expected path (default: '/app')
            timeout: Timeout in milliseconds
            
        Raises:
            AssertionError: If redirect didn't happen
        """
        try:
            await self.page.wait_for_url(f"**{expected_path}", timeout=timeout)
        except PlaywrightTimeoutError:
            current_url = self.page.url
            if '/signin' in current_url:
                # Check for error message
                error_msg = await SignInPage(self.page).get_error_message()
                if error_msg:
                    raise AssertionError(f"Login failed with error: {error_msg}")
                raise AssertionError("Login failed: Still on signin page but no error message visible")
            else:
                raise AssertionError(f"Login failed: Unexpected navigation to {current_url}")
    
    async def wait_for_page_load(self, timeout: int = 30000):
        """Wait for app page to fully load.
        
        Args:
            timeout: Timeout in milliseconds
        """
        await self.page.wait_for_load_state("networkidle", timeout=timeout)
        await asyncio.sleep(1)
    
    async def verify_chat_panel_visible(self, timeout: int = 10000):
        """Verify chat panel is visible.
        
        Args:
            timeout: Timeout in milliseconds
            
        Raises:
            AssertionError: If chat panel is not visible
        """
        chat_panel = self.page.locator('[data-testid="chat-panel"]')
        await expect(chat_panel).to_be_visible(timeout=timeout)
    
    async def verify_user_email_displayed(self, email: str, timeout: int = 5000):
        """Verify user email is displayed.
        
        Args:
            email: Expected email address
            timeout: Timeout in milliseconds
            
        Raises:
            AssertionError: If email is not displayed
        """
        # Try to find email in header
        user_info = self.page.locator(f'text=/{email}/i')
        if await user_info.first.is_visible(timeout=timeout):
            return
        
        # Try clicking profile menu to see if email is in dropdown
        try:
            profile_button = self.page.locator('text=/User1|User2|user1|user2/i').first
            if await profile_button.is_visible(timeout=timeout):
                await profile_button.click()
                await asyncio.sleep(0.5)
                email_in_dropdown = self.page.locator(f'text={email}')
                if await email_in_dropdown.is_visible(timeout=timeout):
                    return
        except PlaywrightTimeoutError:
            pass
        
        # If we get here, email was not found
        raise AssertionError(f"User email '{email}' is not displayed in header or profile menu")
    
    async def verify_app_container_visible(self, timeout: int = 30000):
        """Verify app container is visible.
        
        Args:
            timeout: Timeout in milliseconds
        """
        await self.page.wait_for_selector('[data-testid="app-container"]', state="visible", timeout=timeout)


class ChatPanel:
    """Page object for the chat panel."""
    
    def __init__(self, page: Page):
        """Initialize chat panel object.
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    async def wait_for_chat_ready(self, timeout: int = 10000):
        """Wait for chat panel to be ready.
        
        Args:
            timeout: Timeout in milliseconds
        """
        await self.page.wait_for_selector('[data-testid="chat-panel"]', state="visible", timeout=timeout)
        await asyncio.sleep(1)
    
    async def type_message(self, message: str):
        """Type a message in the chat input.
        
        Args:
            message: Message text
        """
        # Find chat textarea (the chat input is a textarea with placeholder "Chat, visualize, or build...")
        chat_input = self.page.locator('textarea[placeholder*="Chat"], textarea').first
        await chat_input.wait_for(state="visible", timeout=10000)
        await chat_input.fill(message)
        await asyncio.sleep(0.5)
    
    async def send_message(self, message: Optional[str] = None):
        """Send a message.
        
        Args:
            message: Optional message to type before sending
        """
        if message:
            await self.type_message(message)
        
        # Find and click send button - it's a submit button in the form with Send icon
        # Try multiple selectors to find the send button
        send_button = self.page.locator(
            'button[type="submit"]:not([disabled]), '
            'button:has(svg):has-text("Send"), '
            'form button[type="submit"]'
        ).first
        await send_button.wait_for(state="visible", timeout=10000)
        await send_button.click()
        await asyncio.sleep(2)  # Wait longer for message to be sent and appear
    
    async def verify_message_in_history(self, message: str, timeout: int = 10000):
        """Verify message appears in chat history.
        
        Args:
            message: Message text to verify
            timeout: Timeout in milliseconds
            
        Raises:
            AssertionError: If message is not found
        """
        message_locator = self.page.locator(f'text={message}').first
        await expect(message_locator).to_be_visible(timeout=timeout)


class ProfileMenu:
    """Page object for the profile menu."""
    
    def __init__(self, page: Page):
        """Initialize profile menu object.
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    async def open_menu(self):
        """Open the profile menu."""
        # Try to find profile menu button by data-testid first, then by text
        profile_button = self.page.locator('[data-testid="profile-menu"]').first
        if not await profile_button.is_visible(timeout=2000):
            # Fallback to finding button with user text
            profile_button = self.page.locator('button').filter(has_text=re.compile(r'User', re.I)).first
        await profile_button.click()
        await asyncio.sleep(0.5)
    
    async def verify_email_in_menu(self, email: str, timeout: int = 5000):
        """Verify email is displayed in profile menu.
        
        Args:
            email: Expected email address
            timeout: Timeout in milliseconds
        """
        await self.open_menu()
        email_locator = self.page.locator(f'text={email}')
        await expect(email_locator).to_be_visible(timeout=timeout)
    
    async def sign_out(self):
        """Sign out from the application."""
        await self.open_menu()
        # Find sign out button by text (case insensitive)
        signout_button = self.page.locator('button, a').filter(has_text=re.compile(r'sign out|logout', re.I)).first
        await signout_button.wait_for(state="visible", timeout=5000)
        await signout_button.click()
        await asyncio.sleep(1)
