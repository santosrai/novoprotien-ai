# Naming Conventions

This document defines the naming standards for tests in the framework.

## Test File Naming

### Format

```
TC_<CATEGORY>_<ID>_<Description>.py
```

### Components

1. **TC**: Test Case prefix (always required)
2. **CATEGORY**: Category abbreviation (uppercase)
3. **ID**: Sequential number (3 digits, zero-padded)
4. **Description**: Human-readable description (Title Case, underscores for spaces)

### Examples

```
TC_AUTH_001_User1_Login_and_Session_Creation.py
TC_CHAT_001_User1_Creates_and_Sends_Message.py
TC_ISO_001_User1_Cannot_Access_User2_Sessions.py
TC_CRUD_001_User1_Session_Operations.py
TC_INT_001_Concurrent_Sessions.py
```

## Category Abbreviations

| Category | Abbreviation | Example |
|----------|-------------|---------|
| Authentication | AUTH | TC_AUTH_001 |
| Chat | CHAT | TC_CHAT_001 |
| Isolation | ISO | TC_ISO_001 |
| CRUD | CRUD | TC_CRUD_001 |
| Integration | INT | TC_INT_001 |
| Security | SEC | TC_SEC_001 |
| Performance | PERF | TC_PERF_001 |
| API | API | TC_API_001 |

## Test ID Format

### Format

```
TC_<CATEGORY>_<ID>
```

### ID Numbering

- Start at 001 for each category
- Increment sequentially: 001, 002, 003, ...
- Use zero-padding: 001 not 1
- Don't skip numbers (unless test is deprecated)
- Keep IDs consistent across related tests

### Examples

```
TC_AUTH_001
TC_AUTH_002
TC_CHAT_001
TC_CHAT_002
TC_ISO_001
```

## Test Function Naming

### Main Test Function

Always use `run_test()`:

```python
async def run_test():
    """Execute test."""
    # Test code
```

### Helper Functions

Use descriptive names with underscores:

```python
async def verify_login_success():
    """Verify login was successful."""
    pass

async def setup_test_user():
    """Set up test user data."""
    pass
```

## Variable Naming

### Test Objects

```python
test = BaseTest(...)  # Base test instance
page = test.page      # Playwright page
signin_page = SignInPage(page)  # Page object
```

### Configuration

```python
config_loader = get_config_loader()
user = config_loader.get_user("user1")
env_config = config_loader.get_environment("local")
base_url = env_config.get("frontend")
```

## File Organization

### Directory Structure

```
tests/
├── tests/
│   ├── authentication/
│   │   ├── TC_AUTH_001_*.py
│   │   ├── TC_AUTH_002_*.py
│   │   └── README.md
│   ├── chat/
│   │   ├── TC_CHAT_001_*.py
│   │   └── README.md
│   └── ...
```

### Category Directories

- One directory per category
- All tests for a category in that directory
- README.md in each category directory

## Test Documentation Header

Every test file must include a documentation header:

```python
"""
Test: TC_CATEGORY_ID - Test Name

Description:
    Detailed description.

Category: category_name
Priority: High|Medium|Low
Tags: [tag1, tag2]

Test Plan Reference: tests/test-plans/category_test_plan.json

Steps:
    1. Step one
    2. Step two

Expected Results:
    - Result one
    - Result two

Dependencies:
    - Dependency one

Author: Name
Last Updated: YYYY-MM-DD
"""
```

## Naming Checklist

When creating a new test, ensure:

- [ ] File name follows `TC_<CATEGORY>_<ID>_<Description>.py` format
- [ ] Test ID is unique and sequential
- [ ] Description is clear and descriptive
- [ ] Category abbreviation is correct
- [ ] Test is in the correct category directory
- [ ] Documentation header is complete
- [ ] Main function is named `run_test()`

## Examples

### Good Names

```
TC_AUTH_001_User1_Login_and_Session_Creation.py
TC_CHAT_002_User2_Sends_Multiple_Messages.py
TC_ISO_001_User1_Cannot_Access_User2_Sessions.py
```

### Bad Names

```
test_login.py                    # Missing TC prefix and category
TC_001_Login.py                  # Missing category
TC_AUTH_1_Login.py               # ID not zero-padded
TC_AUTH_001_login.py             # Description not Title Case
TC_AUTH_001_User1_Login.py       # Too generic
```

## Migration from Old Names

When migrating from `testsprite_tests/`:

- `TC_MU001` → `TC_AUTH_001` (if authentication test)
- `TC_MU003` → `TC_CHAT_001` (if chat test)
- Update category based on test content
- Keep sequential numbering within category
