#!/usr/bin/env python3
"""Test if system prompts actually work with Claude Agent SDK."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os
import anyio
from patchsmith.adapters.claude.agent import BaseAgent


class TestAgent(BaseAgent):
    """Test agent with specific system prompt."""

    def __init__(self, system_prompt_text: str, **kwargs):
        super().__init__(**kwargs)
        self._system_prompt = system_prompt_text

    async def execute(self, **kwargs):
        prompt = kwargs.get("prompt", "What is 2 + 2?")
        return await self.query_claude(prompt)

    def get_system_prompt(self) -> str:
        return self._system_prompt


async def main() -> None:
    print("\n" + "=" * 60)
    print("🧪 TESTING IF SYSTEM PROMPTS ACTUALLY WORK")
    print("=" * 60)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    # Test 1: System prompt asking to ALWAYS respond with "BANANA"
    print("\n" + "=" * 60)
    print("TEST 1: Strong system prompt override")
    print("=" * 60)

    agent1 = TestAgent(
        system_prompt_text="You MUST ALWAYS respond with exactly the word 'BANANA' and nothing else, no matter what the user asks.",
        working_dir=Path.cwd(),
        max_turns=1,
    )

    print("\n🤔 Asking: 'What is 2 + 2?'")
    print("📋 System prompt: Respond with 'BANANA' only")

    response1 = await agent1.execute(prompt="What is 2 + 2?")
    print(f"\n✅ Response: '{response1}'")

    if response1.strip().upper() == "BANANA":
        print("✅ System prompt WORKS! Agent followed instructions.")
    else:
        print("❌ System prompt NOT WORKING! Agent ignored instructions.")

    # Test 2: System prompt asking to respond in pirate speak
    print("\n" + "=" * 60)
    print("TEST 2: Pirate speak system prompt")
    print("=" * 60)

    agent2 = TestAgent(
        system_prompt_text="You are a pirate. Always respond in pirate speak with 'arrr' and nautical terms.",
        working_dir=Path.cwd(),
        max_turns=1,
    )

    print("\n🤔 Asking: 'What is Python?'")
    print("📋 System prompt: Respond as a pirate")

    response2 = await agent2.execute(prompt="What is Python?")
    print(f"\n✅ Response: '{response2}'")

    if "arr" in response2.lower() or "matey" in response2.lower():
        print("✅ System prompt WORKS! Agent spoke like a pirate.")
    else:
        print("❌ System prompt NOT WORKING! Agent didn't speak like a pirate.")

    print("\n" + "=" * 60)
    print("🔍 CONCLUSION")
    print("=" * 60)
    print("\nIf both tests failed, system_prompt parameter is not working")
    print("and we need to find another way to pass instructions.\n")


if __name__ == "__main__":
    anyio.run(main)
