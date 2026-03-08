import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv("server/.env")

from server.agents.runner import run_react_agent_stream

async def test():
    print("starting stream...")
    async for chunk in run_react_agent_stream(
        user_text="hi",
        current_code=None,
        history=[],
        selection=None,
        selections=None,
    ):
        print(chunk)

if __name__ == "__main__":
    asyncio.run(test())
