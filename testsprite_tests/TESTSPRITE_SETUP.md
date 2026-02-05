# TestSprite Setup Guide for Local Testing

## Prerequisites

1. **Ensure both servers are running:**
   ```bash
   # Terminal 1: Start backend
   cd server && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8787
   
   # Terminal 2: Start frontend
   npm run dev
   ```

2. **Verify servers are accessible:**
   ```bash
   curl http://localhost:3000/signin
   curl http://localhost:8787/api/health
   ```

## TestSprite Configuration

The configuration file is at: `testsprite_tests/tmp/config.json`

### Key Settings:
- **localEndpoint**: `http://localhost:3000` - Your local frontend URL
- **type**: `frontend` - Testing frontend application
- **scope**: `codebase` - Test entire codebase

### Proxy/Tunnel:
TestSprite uses a tunnel to access your localhost. The proxy URL is automatically generated and should be in the config file.

## Common Issues & Solutions

### Issue 1: "Failed to re-run the test"
**Cause**: TestSprite can't access localhost through the tunnel
**Solution**: 
- Verify both servers are running
- Check firewall isn't blocking the tunnel
- Ensure servers are bound to `0.0.0.0` not just `localhost`

### Issue 2: "Page not loading" or "Blank page"
**Cause**: Application taking too long to load or React not rendering
**Solution**:
- The config now includes 30-second timeouts
- Tests wait for `data-testid` attributes
- Tests wait for `data-form-ready` attributes
- Tests include explicit sleep delays

### Issue 3: "ERR_INVALID_HTTP_RESPONSE" for MolStar files
**Cause**: Vite dev server not serving files correctly through tunnel
**Solution**:
- This is often a tunnel/proxy issue
- Try restarting both servers
- Check Vite config allows external connections

### Issue 4: Elements not found
**Cause**: React hasn't finished rendering
**Solution**:
- Tests now wait for `data-testid` attributes
- Tests wait for `data-form-ready="true"`
- Tests include multiple wait strategies

## Running Tests

### Bootstrap Tests (First Time):
```bash
cd /Users/alizabista/Downloads/Dev-Folder/novoprotien-ai
node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js bootstrapTests
```

### Generate and Execute Tests:
```bash
node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js generateCodeAndExecute
```

### Re-run Tests:
```bash
node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js reRunTests
```

## Wait Strategy Details

The updated configuration includes:

1. **30-second timeouts** for all operations
2. **Explicit waits** for data-testid attributes
3. **Network idle waits** before interacting
4. **Sleep delays** after navigation and interactions
5. **Ready state checks** using data attributes

## Debugging Failed Tests

1. **Check test visualization**: Each test has a link to a video recording
2. **Review browser console**: Tests capture console errors
3. **Check screenshots**: Tests should take screenshots on failure
4. **Verify tunnel**: Ensure TestSprite can reach localhost:3000

## Server Configuration

### Backend (FastAPI):
```python
# In server/app.py, ensure:
uvicorn.run(app, host="0.0.0.0", port=8787)  # Not "127.0.0.1"
```

### Frontend (Vite):
```typescript
// In vite.config.ts, ensure:
server: {
  host: '0.0.0.0',  // Allow external connections
  port: 3000,
}
```

## Next Steps

1. Ensure both servers are running
2. Verify they're accessible
3. Run bootstrap tests
4. Execute test suite
5. Review results and fix any issues
