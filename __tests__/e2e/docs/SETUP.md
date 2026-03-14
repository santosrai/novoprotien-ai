# Test Framework Setup Guide

This guide will help you set up the Playwright testing framework for the NovoProtein AI project.

## Prerequisites

1. **Python 3.8+** installed
2. **Node.js** and npm installed (for running the application)
3. **Playwright** installed: `pip install playwright && playwright install chromium`

## Installation Steps

### 1. Install Dependencies

```bash
# Install Playwright
pip install playwright

# Install browser binaries
playwright install chromium
```

### 2. Verify Configuration

Check that configuration files exist:

```bash
ls tests/config/
# Should show: config.json, test-users.json, environments.json
```

### 3. Start Application Servers

Before running tests, ensure both frontend and backend are running:

**Terminal 1 - Backend:**
```bash
cd server
source venv/bin/activate  # or .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8787
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

The application should be accessible at:
- Frontend: http://localhost:3000
- Backend: http://localhost:8787

### 4. Verify Setup

Test that the setup is working:

```bash
# Run a single test
python3 tests/tests/authentication/TC_AUTH_001_User1_Login_and_Session_Creation.py

# Or use the test runner
python3 tests/utils/test_runner.py --test-id TC_AUTH_001
```

## Configuration

### Environment Configuration

Edit `tests/config/config.json` to adjust:
- Timeouts
- Browser settings (headless mode, viewport size)
- Wait strategies
- Execution settings

### Test Users

Edit `tests/config/test-users.json` to add or modify test users:
- `user1`: Default test user
- `user2`: Secondary test user

### Environment Settings

Edit `tests/config/environments.json` to configure different environments:
- `local`: Local development
- `staging`: Staging environment
- `production`: Production (use with caution!)

## Running Tests

### Run All Tests

```bash
python3 tests/utils/test_runner.py
```

### Run Tests by Category

```bash
# Authentication tests only
python3 tests/utils/test_runner.py --category authentication

# Chat tests only
python3 tests/utils/test_runner.py --category chat
```

### Run Specific Test

```bash
python3 tests/utils/test_runner.py --test-id TC_AUTH_001
```

### Run Tests Matching Pattern

```bash
python3 tests/utils/test_runner.py --pattern "AUTH"
```

### Run Tests in Parallel

```bash
python3 tests/utils/test_runner.py --parallel
```

### Run Tests Against Different Environment

```bash
python3 tests/utils/test_runner.py --environment staging
```

## Test Reports

After running tests, reports are generated in `tests/reports/latest/`:
- `test_results.json`: Machine-readable JSON report
- `test_report.md`: Human-readable Markdown report
- `screenshots/`: Screenshots of failed tests

## Troubleshooting

### Tests Fail with "Connection Refused"

- Ensure both frontend and backend servers are running
- Check that servers are bound to `0.0.0.0` not just `localhost`
- Verify ports 3000 and 8787 are not in use by other applications

### Tests Fail with "Element Not Found"

- Increase timeout in `tests/config/config.json`
- Check that React has finished rendering (tests wait for `data-testid` attributes)
- Verify the application is loading correctly in a manual browser

### Tests Fail with "Login Failed"

- Verify test users exist in the database
- Check backend logs for authentication errors
- Ensure backend is running and accessible

### Browser Doesn't Open

- Set `"headless": false` in `tests/config/config.json`
- Check that Playwright browsers are installed: `playwright install chromium`

## Next Steps

- Read [TESTING_GUIDE.md](TESTING_GUIDE.md) to learn how to write tests
- Review [NAMING_CONVENTIONS.md](NAMING_CONVENTIONS.md) for test naming standards
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
