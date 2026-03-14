# Authentication Tests

This directory contains tests for user authentication functionality.

## Test List

### TC_AUTH_001 - User1 Login and Session Creation
- **Description**: Verify User1 can successfully log in and create a chat session
- **Priority**: High
- **Tags**: login, session, user1

### TC_AUTH_002 - User2 Login and Session Creation
- **Description**: Verify User2 can successfully log in and create a chat session
- **Priority**: High
- **Tags**: login, session, user2

## Common Patterns

### Login Flow
All authentication tests follow this pattern:

1. Navigate to `/signin` page
2. Wait for form to be ready
3. Fill in credentials
4. Click sign in button
5. Verify redirect to `/app`
6. Verify chat panel is visible
7. Verify user email is displayed

### Using Page Objects

```python
from page_objects import SignInPage, AppPage

signin_page = SignInPage(page)
await signin_page.navigate()
await signin_page.login(email, password)

app_page = AppPage(page)
await app_page.verify_redirect()
await app_page.verify_chat_panel_visible()
```

## Test Users

Test users are configured in `tests/config/test-users.json`:
- `user1`: user1@gmail.com / test12345
- `user2`: user2@gmail.com / test12345

## Known Issues

None at this time.
