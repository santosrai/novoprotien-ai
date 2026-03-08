# Troubleshooting Guide

Common issues and solutions when running Playwright tests.

## Connection Issues

### "Connection Refused" or "ERR_CONNECTION_REFUSED"

**Symptoms:**
- Tests fail immediately with connection errors
- Browser cannot reach localhost:3000 or localhost:8787

**Solutions:**
1. Verify both servers are running:
   ```bash
   # Check frontend
   curl http://localhost:3000/signin
   
   # Check backend
   curl http://localhost:8787/api/health
   ```

2. Ensure servers are bound to `0.0.0.0` not just `localhost`:
   - Frontend: Check `vite.config.ts` has `host: '0.0.0.0'`
   - Backend: Check uvicorn is started with `--host 0.0.0.0`

3. Check firewall isn't blocking connections

4. Verify ports are not in use:
   ```bash
   lsof -i :3000
   lsof -i :8787
   ```

## Element Not Found

### "Element not found" or "Timeout waiting for selector"

**Symptoms:**
- Tests fail waiting for elements
- Selectors not found even though page loads

**Solutions:**
1. Increase timeout in `tests/config/config.json`:
   ```json
   {
     "testSettings": {
       "defaultTimeout": 60000  // Increase from 30000
     }
   }
   ```

2. Wait for React to render:
   - Tests should use page objects that handle React waiting
   - Check that `data-testid` attributes are present in components

3. Verify element selectors:
   ```bash
   # Open browser manually and check
   # Inspect element to verify data-testid exists
   ```

4. Check for JavaScript errors:
   - Open browser console during test
   - Look for React errors or missing dependencies

5. Wait for network idle:
   - Tests should wait for `networkidle` after navigation
   - Check that all resources (CSS, JS) are loaded

## Login Failures

### "Login failed" or "Invalid credentials"

**Symptoms:**
- Tests fail at login step
- User cannot authenticate

**Solutions:**
1. Verify test users exist in database:
   ```bash
   # Check database or backend logs
   ```

2. Check test user credentials in `tests/config/test-users.json`:
   ```json
   {
     "users": [
       {
         "id": "user1",
         "email": "user1@gmail.com",
         "password": "test12345"
       }
     ]
   }
   ```

3. Verify backend authentication is working:
   ```bash
   curl -X POST http://localhost:8787/api/auth/signin \
     -H "Content-Type: application/json" \
     -d '{"email":"user1@gmail.com","password":"test12345"}'
   ```

4. Check backend logs for authentication errors

5. Ensure database is initialized with test users

## Browser Issues

### Browser doesn't open or crashes

**Symptoms:**
- Tests fail immediately
- No browser window appears
- Browser process crashes

**Solutions:**
1. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

2. Check headless mode in `tests/config/config.json`:
   ```json
   {
     "testSettings": {
       "headless": false  // Set to false to see browser
     }
   }
   ```

3. Check system requirements:
   - Sufficient memory
   - Graphics drivers up to date
   - No conflicting browser processes

4. Try different browser:
   ```json
   {
     "testSettings": {
       "browser": "firefox"  // or "webkit"
     }
   }
   ```

## React Rendering Issues

### "Page loads but elements not visible"

**Symptoms:**
- Page HTML loads
- React components not rendering
- Tests timeout waiting for elements

**Solutions:**
1. Increase React wait timeout:
   ```json
   {
     "waitStrategies": {
       "reactTimeout": 10000  // Increase from 5000
     }
   }
   ```

2. Wait for form ready attributes:
   - Tests should wait for `data-form-ready="true"`
   - Check that components set this attribute

3. Check for React errors:
   - Open browser console
   - Look for React rendering errors
   - Check for missing dependencies

4. Verify lazy loading:
   - Some components may be lazy loaded
   - Tests should wait for components to load

## Test Execution Issues

### "Test module not found" or "Import errors"

**Symptoms:**
- Tests fail to import
- ModuleNotFoundError

**Solutions:**
1. Check Python path:
   ```python
   # Tests should add fixtures to path
   sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
   ```

2. Verify file structure:
   ```
   tests/
   ├── fixtures/
   │   ├── base_test.py
   │   └── page_objects.py
   └── tests/
       └── authentication/
           └── TC_AUTH_001_*.py
   ```

3. Check imports in test file:
   ```python
   from base_test import BaseTest
   from page_objects import SignInPage
   ```

## Report Generation Issues

### "Reports not generated" or "Permission denied"

**Symptoms:**
- Tests run but no reports created
- Permission errors when writing reports

**Solutions:**
1. Check reports directory exists:
   ```bash
   ls -la tests/reports/latest/
   ```

2. Verify write permissions:
   ```bash
   chmod -R 755 tests/reports/
   ```

3. Check disk space:
   ```bash
   df -h
   ```

## Performance Issues

### "Tests run very slowly"

**Symptoms:**
- Tests take a long time to complete
- Timeouts occur frequently

**Solutions:**
1. Reduce wait times (if safe):
   ```json
   {
     "testSettings": {
       "defaultTimeout": 15000  // Reduce from 30000
     }
   }
   ```

2. Run tests in parallel:
   ```bash
   python3 tests/utils/test_runner.py --parallel
   ```

3. Use headless mode:
   ```json
   {
     "testSettings": {
       "headless": true
     }
   }
   ```

4. Optimize application:
   - Reduce bundle size
   - Enable lazy loading
   - Optimize React rendering

## Getting Help

If issues persist:

1. Check test reports in `tests/reports/latest/test_report.md`
2. Review screenshots in `tests/reports/latest/screenshots/`
3. Check application logs (frontend and backend)
4. Review browser console during test execution
5. Verify configuration files are correct
6. Check that all dependencies are installed

## Debug Mode

Enable debug mode for more information:

```python
# In test file
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export DEBUG=1
python3 tests/utils/test_runner.py
```
