#!/usr/bin/env python3
"""
Test the chat stream endpoint: sign in, then call /api/agents/route/stream.
Run from project root: ./.venv/bin/python test_chat_stream.py
"""
import asyncio
import json
import os
import sys

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    base = "http://localhost:8787"
    
    # 1. Sign up then sign in (use env or default test user)
    email = os.getenv("TEST_EMAIL", "teststream@test.com")
    password = os.getenv("TEST_PASSWORD", "testpass123")
    username = "teststream"
    
    async with __import__("httpx").AsyncClient(timeout=90.0) as client:
        print("1. Signing up (in case user doesn't exist)...")
        try:
            r = await client.post(f"{base}/api/auth/signup", json={"email": email, "username": username, "password": password})
            if r.status_code not in (200, 400):  # 400 = already exists
                print(f"   Signup: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"   Signup error: {e}")
        
        print("2. Signing in...")
        try:
            r = await client.post(f"{base}/api/auth/signin", json={"email": email, "password": password})
            if r.status_code != 200:
                print(f"   Signin failed: {r.status_code} {r.text[:200]}")
                return
            data = r.json()
            token = data.get("access_token")
            if not token:
                print("   No access_token in response")
                return
            print("   OK")
        except Exception as e:
            print(f"   Error: {e}")
            return

        # 3. Call stream endpoint
        print("3. Calling POST /api/agents/route/stream...")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"input": "hi", "agentId": "react"}
        
        try:
            async with client.stream("POST", f"{base}/api/agents/route/stream", json=payload, headers=headers) as resp:
                print(f"   Status: {resp.status_code}")
                if resp.status_code != 200:
                    body = await resp.aread()
                    print(f"   Body: {body.decode()[:500]}")
                    return
                count = 0
                async for line in resp.aiter_lines():
                    if line.strip():
                        count += 1
                        try:
                            obj = json.loads(line)
                            t = obj.get("type", "?")
                            if t == "content":
                                txt = (obj.get("data") or {}).get("text", "")[:40]
                                print(f"   [{count}] content: {txt!r}...")
                            elif t == "complete":
                                print(f"   [{count}] complete")
                                break
                            elif t == "error":
                                print(f"   [{count}] error: {obj.get('data', {})}")
                                break
                            else:
                                print(f"   [{count}] {t}")
                        except json.JSONDecodeError:
                            print(f"   [{count}] (raw) {line[:80]}")
                print(f"   Total chunks: {count}")
        except Exception as e:
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
