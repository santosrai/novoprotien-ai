# TestSprite Quick Start Guide

## ⚠️ IMPORTANT: Restart Servers After Config Changes

I've updated `vite.config.ts` to allow external connections. **You must restart your Vite dev server** for the changes to take effect.

## Step 1: Restart Servers

### Stop current servers (Ctrl+C in their terminals), then:

**Terminal 1 - Backend:**
```bash
cd server
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8787
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

The Vite server will now bind to `0.0.0.0` instead of just `localhost`, allowing TestSprite's tunnel to access it.

## Step 2: Verify Setup

Run the verification script:
```bash
./testsprite_tests/VERIFY_SETUP.sh
```

You should see:
- ✅ Frontend (port 3000) is accessible
- ✅ Backend (port 8787) is accessible
- ✅ Frontend is bound to 0.0.0.0 (accessible externally)
- ✅ Backend is bound to 0.0.0.0 (accessible externally)

## Step 3: Run Tests

### Option A: Generate and Execute Tests (Recommended)
```bash
node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js generateCodeAndExecute
```

### Option B: Re-run Existing Tests
```bash
node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js reRunTests
```

## What I Fixed

1. **Vite Configuration**: Added `host: '0.0.0.0'` to allow external connections
2. **TestSprite Config**: Updated with detailed wait strategies:
   - 30-second timeouts (increased from 5-10 seconds)
   - Explicit waits for `data-testid` attributes
   - Network idle waits before interactions
   - Sleep delays after navigation and clicks
   - Ready state checks using data attributes

3. **Wait Strategy Pattern**: Tests now follow this pattern:
   ```python
   # Navigate with long timeout
   await page.goto('http://localhost:3000/signin', timeout=30000)
   await asyncio.sleep(5)  # Wait for React
   await page.wait_for_load_state('networkidle', timeout=30000)
   
   # Wait for form ready
   await page.wait_for_selector('[data-form-ready="true"]', timeout=30000)
   
   # Wait for specific elements
   await page.wait_for_selector('[data-testid="email-input"]', timeout=30000, state='visible')
   ```

## Troubleshooting

### Issue: "Failed to re-run the test"
- **Solution**: Ensure both servers are running and bound to `0.0.0.0`
- **Check**: Run `./testsprite_tests/VERIFY_SETUP.sh`

### Issue: "Page not loading" or "Blank page"
- **Solution**: Tests now wait 30 seconds and use multiple wait strategies
- **Check**: Review test visualization videos in TestSprite dashboard

### Issue: "Elements not found"
- **Solution**: Tests now wait for `data-testid` attributes with 30-second timeout
- **Check**: Verify React is rendering by checking browser console

### Issue: "ERR_INVALID_HTTP_RESPONSE for MolStar"
- **Solution**: This is often a tunnel issue. Restart both servers and try again
- **Note**: MolStar is lazy-loaded, so errors might be expected if not used

## Test Configuration Location

- Config file: `testsprite_tests/tmp/config.json`
- Test plan: `testsprite_tests/testsprite_multi_user_chat_test_plan.json`
- Test reports: `testsprite_tests/testsprite-mcp-test-report.md`

## Next Steps

1. ✅ Restart Vite server (to apply `host: '0.0.0.0'` change)
2. ✅ Verify setup with `./testsprite_tests/VERIFY_SETUP.sh`
3. ✅ Run tests with TestSprite
4. ✅ Review results in TestSprite dashboard

## Support

If tests still fail:
1. Check TestSprite dashboard for test visualization videos
2. Review browser console logs in test results
3. Verify tunnel is working (TestSprite should show tunnel URL)
4. Check that both servers are accessible from your machine
