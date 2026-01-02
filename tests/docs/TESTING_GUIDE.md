# Testing Guide

This guide explains how to write and structure tests using the Playwright testing framework.

## Test Structure

Every test file should follow this structure:

```python
"""
Test: TC_CATEGORY_ID - Test Name

Description:
    Detailed description of what the test verifies.

Category: category_name
Priority: High|Medium|Low
Tags: [tag1, tag2, tag3]

Test Plan Reference: tests/test-plans/category_test_plan.json

Steps:
    1. Step description
    2. Another step
    3. Expected result

Expected Results:
    - What should happen
    - What should be visible
    - What should be verified

Dependencies:
    - Required services
    - Required test data
    - Prerequisites

Author: Your Name
Last Updated: YYYY-MM-DD
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
    """Execute test."""
    config_loader = get_config_loader()
    test = BaseTest(
        test_id="TC_CATEGORY_ID",
        test_name="Test Name",
        environment="local"
    )
    
    try:
        await test.setup()
        page = test.page
        
        # Your test steps here
        
        test.mark_passed()
    except Exception as e:
        test.mark_failed(str(e))
        raise
    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(run_test())
```

## Using BaseTest

The `BaseTest` class provides common functionality:

### Setup and Teardown

```python
test = BaseTest(test_id="TC_AUTH_001", test_name="Test Name")
await test.setup()  # Opens browser and creates page
# ... your test code ...
await test.teardown()  # Closes browser and saves results
```

### Recording Steps

```python
test.record_step("Navigate to signin page")
test.record_step("Enter credentials", status="passed")
test.record_step("Verify redirect", status="failed")
```

### Marking Test Status

```python
test.mark_passed()  # Test passed
test.mark_failed("Error message")  # Test failed
test.mark_skipped("Reason")  # Test skipped
```

### Accessing Configuration

```python
config_loader = get_config_loader()
user = config_loader.get_user("user1")
env_config = config_loader.get_environment("local")
base_url = env_config.get("frontend", "http://localhost:3000")
```

## Using Page Objects

Page objects provide reusable page interactions:

### SignInPage

```python
from page_objects import SignInPage

signin_page = SignInPage(page)
await signin_page.navigate("http://localhost:3000")
await signin_page.login("user1@gmail.com", "test12345")
```

### AppPage

```python
from page_objects import AppPage

app_page = AppPage(page)
await app_page.verify_redirect()
await app_page.verify_chat_panel_visible()
await app_page.verify_user_email_displayed("user1@gmail.com")
```

### ChatPanel

```python
from page_objects import ChatPanel

chat_panel = ChatPanel(page)
await chat_panel.wait_for_chat_ready()
await chat_panel.send_message("Hello, world!")
await chat_panel.verify_message_in_history("Hello, world!")
```

## Best Practices

### 1. Use Page Objects

Always use page objects instead of direct Playwright selectors:

```python
# Good
await signin_page.login(email, password)

# Bad
await page.fill('[data-testid="email-input"]', email)
await page.fill('[data-testid="password-input"]', password)
await page.click('[data-testid="signin-button"]')
```

### 2. Record Steps

Record each significant step for better reporting:

```python
test.record_step("Navigate to signin page")
test.record_step("Enter credentials")
test.record_step("Click sign in button")
```

### 3. Use Configuration

Don't hardcode values - use configuration:

```python
# Good
user = config_loader.get_user("user1")
base_url = env_config.get("frontend")

# Bad
email = "user1@gmail.com"
base_url = "http://localhost:3000"
```

### 4. Handle Errors Gracefully

Always mark tests as failed on exceptions:

```python
try:
    # Test code
    test.mark_passed()
except Exception as e:
    test.mark_failed(str(e))
    raise
finally:
    await test.teardown()
```

### 5. Wait for Elements

Use page object methods that handle waiting:

```python
# Good - page objects handle waiting
await signin_page.wait_for_form_ready()

# Bad - direct waits can be flaky
await page.wait_for_selector('[data-testid="email-input"]', timeout=5000)
```

## Test Categories

Organize tests by category in subdirectories:

- `authentication/`: Login, logout, session management
- `chat/`: Chat functionality, messaging
- `isolation/`: User data isolation, security
- `crud/`: Create, read, update, delete operations
- `integration/`: End-to-end workflows

## Example: Complete Test

```python
"""
Test: TC_CHAT_001 - User Sends Message

Description:
    Verify user can send a message in chat.

Category: chat
Priority: High
Tags: [chat, message]
"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from base_test import BaseTest
from page_objects import SignInPage, AppPage, ChatPanel

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
from config_loader import get_config_loader


async def run_test():
    """Execute TC_CHAT_001 test."""
    config_loader = get_config_loader()
    user = config_loader.get_user("user1")
    
    test = BaseTest(
        test_id="TC_CHAT_001",
        test_name="User Sends Message",
        environment="local"
    )
    
    try:
        await test.setup()
        page = test.page
        env_config = config_loader.get_environment("local")
        base_url = env_config.get("frontend", "http://localhost:3000")
        
        # Login
        test.record_step("Login as user")
        signin_page = SignInPage(page)
        await signin_page.navigate(base_url)
        await signin_page.login(user["email"], user["password"])
        
        app_page = AppPage(page)
        await app_page.verify_redirect()
        
        # Send message
        test.record_step("Send chat message")
        chat_panel = ChatPanel(page)
        await chat_panel.wait_for_chat_ready()
        await chat_panel.send_message("Hello, world!")
        
        # Verify
        test.record_step("Verify message in history")
        await chat_panel.verify_message_in_history("Hello, world!")
        
        test.mark_passed()
    except Exception as e:
        test.mark_failed(str(e))
        raise
    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(run_test())
```

## Running Your Test

```bash
# Run directly
python3 tests/tests/chat/TC_CHAT_001_User_Sends_Message.py

# Run with test runner
python3 tests/utils/test_runner.py --test-id TC_CHAT_001
```
