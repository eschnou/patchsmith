#!/usr/bin/env python3
"""Manual test for base agent with real Claude invocation.

This script tests the BaseAgent class with a real Claude Code connection.
Run from project root: poetry run python tests/manual_test_base_agent.py
"""

import sys
from pathlib import Path

# Add src to path so we can import patchsmith
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os

import anyio
from patchsmith.adapters.claude.agent import BaseAgent
from patchsmith.utils.logging import setup_logging


class SimpleTestAgent(BaseAgent):
    """Simple test agent for manual testing."""

    async def execute(self, **kwargs):  # type: ignore
        """Execute a simple test query."""
        prompt = kwargs.get("prompt", "What is 2 + 2?")
        return await self.query_claude(prompt)

    def get_system_prompt(self) -> str:
        """Get system prompt."""
        return "You are a helpful assistant. Answer questions concisely."


async def main() -> None:
    """Test base agent with real Claude."""
    print("\n" + "=" * 60)
    print("🧪 BASE AGENT MANUAL TEST WITH REAL CLAUDE")
    print("=" * 60)

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("\nPlease set your API key:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        print("\nOr create a .env file in the project root:")
        print("  ANTHROPIC_API_KEY=your-api-key-here")
        sys.exit(1)

    print(f"\n✅ API key found: {api_key[:10]}...")

    # Setup logging
    setup_logging(verbose=True)

    # Create test agent
    print("\n📦 Creating test agent...")
    agent = SimpleTestAgent(
        working_dir=Path.cwd(),
        max_turns=3,
        allowed_tools=["Read"],  # Limit tools for safety
    )

    print(f"✅ Agent created: {agent.agent_name}")
    print(f"   Working directory: {agent.working_dir}")
    print(f"   Max turns: {agent.max_turns}")
    print(f"   Allowed tools: {agent.allowed_tools}")

    # Test 1: Simple query
    print("\n" + "=" * 60)
    print("TEST 1: Simple Math Query")
    print("=" * 60)

    try:
        print("\n🤔 Asking Claude: 'What is 2 + 2?'")
        response = await agent.execute(prompt="What is 2 + 2?")

        print("\n✅ Response received:")
        print(f"   Length: {len(response)} characters")
        print(f"   Content: '{response}'")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Test 2: Query with custom system prompt
    print("\n" + "=" * 60)
    print("TEST 2: Query with Custom System Prompt")
    print("=" * 60)

    try:
        print("\n🤔 Asking Claude about Python...")
        response = await agent.query_claude(
            prompt="What is Python? Answer in one sentence.",
            system_prompt="You are a programming expert. Be very concise.",
            max_turns=1,
        )

        print("\n✅ Response received:")
        print(f"   {response}")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Test 3: Working directory validation
    print("\n" + "=" * 60)
    print("TEST 3: Working Directory Validation")
    print("=" * 60)

    try:
        print("\n🔍 Validating working directory...")
        agent.validate_working_dir()
        print("✅ Working directory is valid")

    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\n✅ Base agent successfully communicates with Claude Code")
    print("✅ System prompts work correctly")
    print("✅ Working directory validation works")
    print("\nThe base agent is ready for production use!")
    print()


if __name__ == "__main__":
    anyio.run(main)
