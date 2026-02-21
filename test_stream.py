import asyncio
import httpx
import json

async def test_stream():
    async with httpx.AsyncClient() as client:
        print("Sending request...")
        async with client.stream("POST", "http://0.0.0.0:8787/api/agents/route/stream", json={"input": "hi", "agentId": "react"}) as response:
            print("Response status:", response.status_code)
            async for chunk in response.aiter_lines():
                print("Received chunk:", chunk)

if __name__ == "__main__":
    asyncio.run(test_stream())
