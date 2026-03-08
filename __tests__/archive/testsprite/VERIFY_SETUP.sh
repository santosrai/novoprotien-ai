#!/bin/bash

echo "🔍 Verifying TestSprite Setup..."
echo ""

echo "1. Checking if servers are running..."
if curl -s http://localhost:3000/signin > /dev/null 2>&1; then
    echo "   ✅ Frontend (port 3000) is accessible"
else
    echo "   ❌ Frontend (port 3000) is NOT accessible"
    echo "   Run: npm run dev"
    exit 1
fi

if curl -s http://localhost:8787/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend (port 8787) is accessible"
else
    echo "   ❌ Backend (port 8787) is NOT accessible"
    echo "   Run: cd server && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8787"
    exit 1
fi

echo ""
echo "2. Checking server bindings..."
if netstat -an | grep -q "\.3000.*LISTEN.*0\.0\.0\.0\|\.3000.*LISTEN.*\*"; then
    echo "   ✅ Frontend is bound to 0.0.0.0 (accessible externally)"
else
    echo "   ⚠️  Frontend might only be bound to localhost"
    echo "   Check vite.config.ts has: host: '0.0.0.0'"
fi

if netstat -an | grep -q "\.8787.*LISTEN.*0\.0\.0\.0\|\.8787.*LISTEN.*\*"; then
    echo "   ✅ Backend is bound to 0.0.0.0 (accessible externally)"
else
    echo "   ⚠️  Backend might only be bound to localhost"
    echo "   Ensure uvicorn uses: --host 0.0.0.0"
fi

echo ""
echo "3. Checking TestSprite config..."
if [ -f "testsprite_tests/tmp/config.json" ]; then
    echo "   ✅ TestSprite config exists"
    if grep -q "localEndpoint.*localhost:3000" testsprite_tests/tmp/config.json; then
        echo "   ✅ localEndpoint is configured correctly"
    else
        echo "   ⚠️  localEndpoint might be incorrect"
    fi
else
    echo "   ❌ TestSprite config not found"
    echo "   Run: npm run test:bootstrap (or equivalent)"
    exit 1
fi

echo ""
echo "4. Testing page load..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/signin)
if [ "$RESPONSE" = "200" ]; then
    echo "   ✅ Signin page returns 200 OK"
else
    echo "   ⚠️  Signin page returned: $RESPONSE"
fi

echo ""
echo "✅ Setup verification complete!"
echo ""
echo "Next steps:"
echo "1. Ensure both servers are running (see above)"
echo "2. Run TestSprite tests:"
echo "   node /Users/alizabista/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js generateCodeAndExecute"
echo ""
