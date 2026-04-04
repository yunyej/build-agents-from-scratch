"""
Chapter 3 — Agent pattern: OpenAI tool calling + loop until the model answers.

The multiply tool runs in your process; the model decides when to call it.
Run: python ch03c_agent_openai_tools.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env


def multiply(a: int, b: int) -> int:
    return a * b


TOOLS: dict[str, Any] = {"multiply": multiply}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "Multiply two integers a and b. Use for arithmetic the model should not guess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        },
    }
]


def assistant_to_message_dict(msg) -> dict[str, Any]:
    """Build a dict the Chat Completions API accepts for the next turn."""
    out: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content or "",
    }
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return out


def run_agent_openai(user_text: str, max_steps: int = 8) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You can call the function multiply when you need exact integer products. "
                "After tools return, give a short final answer to the user."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=messages,
            tools=TOOLS_SPEC,
            tool_choice="auto",
        )
        msg = completion.choices[0].message
        messages.append(assistant_to_message_dict(msg))

        if not msg.tool_calls:
            return (msg.content or "").strip()

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name not in TOOLS:
                out = f"error: unknown tool {name!r}"
            else:
                fn = TOOLS[name]
                out = str(fn(**args))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out,
                }
            )

    return "Stopped: max_steps exceeded."


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    q = "What is 24 * 17? Use the multiply tool if it helps."
    print(run_agent_openai(q))


if __name__ == "__main__":
    main()
