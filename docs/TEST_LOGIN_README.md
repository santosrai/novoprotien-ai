# Login Test with Playwright

A simple Playwright test script to verify user login functionality.

## Prerequisites

1. **Install Playwright** (if not already installed):
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Start the application**:
   ```bash
   # Start both frontend and backend
   npm run dev:all
   
   # Or start separately:
   # Terminal 1: Backend
   npm run start:server
   
   # Terminal 2: Frontend
   npm run dev
   ```

   The app should be running on:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8787

## Running the Test

### Option 1: Direct execution
```bash
python3 test_login.py
```

### Option 2: Using Python module
```bash
python3 -m pytest test_login.py -v
```

### Option 3: With asyncio
```bash
python3 -c "import asyncio; from test_login import test_login; asyncio.run(test_login())"
```

## Test Credentials

The test uses these default credentials:
- **Email**: `user1@gmail.com`
- **Password**: `test12345`

To test with different credentials, edit the `test_login.py` file and change the values in the `test_login()` function.

## What the Test Does

1. ✅ Navigates to `/signin` page
2. ✅ Waits for the signin form to be ready
3. ✅ Fills in email and password fields
4. ✅ Clicks the sign in button
5. ✅ Verifies redirect to `/app` page
6. ✅ Checks that chat panel is visible (session created)
7. ✅ Verifies user email is displayed

## Expected Output

```
🚀 Starting Playwright Login Test
Make sure the app is running on http://localhost:3000

============================================================
Testing Login Flow
============================================================

[1/5] Navigating to /signin page...
✅ Page loaded

[2/5] Waiting for signin form...
✅ Signin form is ready

[3/5] Entering credentials...
✅ Credentials entered

[4/5] Clicking sign in button...
✅ Sign in button clicked

[5/5] Waiting for redirect to /app...
✅ Successfully redirected to /app

============================================================
Verifying Login Success
============================================================
✅ URL is correct: /app
✅ Chat panel is visible - session created
✅ User email/username is displayed

============================================================
✅✅✅ LOGIN TEST PASSED!
============================================================
```

## Troubleshooting

### Test fails with "Connection refused"
- Make sure the app is running on `http://localhost:3000`
- Check that both frontend and backend servers are started

### Test fails with "Element not found"
- The page might be loading slowly - increase timeout values in the script
- Check browser console for JavaScript errors
- Verify that `data-testid` attributes are present in the signin form

### Test fails with "Login failed"
- Verify the test credentials exist in the database
- Check backend logs for authentication errors
- Ensure the backend is running on port 8787

### Browser doesn't open (headless mode)
- The script uses `headless=False` by default to show the browser
- If you want headless mode, change `headless=False` to `headless=True` in the script

## Customization

You can customize the test by modifying these variables in `test_login()`:

```python
# Change credentials
await email_input.fill('your-email@example.com')
await password_input.fill('your-password')

# Change URL
await page.goto('http://localhost:3000/signin', ...)

# Change timeout
context.set_default_timeout(60000)  # 60 seconds

# Enable headless mode
browser = await playwright.chromium.launch(headless=True)
```

## Related Tests

For more comprehensive tests, see:
- `testsprite_tests/TC_MU001_User1_Login_and_Session_Creation.py` - Full test suite
- `testsprite_tests/testsprite_frontend_test_plan.json` - Test plan
