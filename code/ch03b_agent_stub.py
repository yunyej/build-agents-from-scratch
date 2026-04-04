"""
Chapter 3 — Same agent loop as the chapter, with a stub model (no API key).

Shows observe → think → act without network calls.
Run: python ch03b_agent_stub.py
"""

from __future__ import annotations

from typing import Any, Callable


def multiply(a: int, b: int) -> int:
    return a * b


TOOLS: dict[str, Callable[..., Any]] = {"multiply": multiply}


def model_step(messages: list[dict]) -> dict:
    """
    Returns either:
      {"kind": "final", "text": str}
      {"kind": "tool", "name": str, "arguments": dict}
    """
    # last_user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    last_user = None
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"]
            break
    tool_results = [m for m in messages if m["role"] == "tool"]

    if not tool_results and "24" in last_user and "17" in last_user:
        return {"kind": "tool", "name": "multiply", "arguments": {"a": 24, "b": 17}}

    if tool_results:
        return {
            "kind": "final",
            "text": "24 * 17 = 408 (computed with the multiply tool).",
        }

    return {"kind": "final", "text": "I am not sure how to help without a tool."}


def run_agent(user_text: str, max_steps: int = 8) -> str:
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You may call tools to help the user. "
                "When you have the result, reply with a short final message."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        step = model_step(messages)

        if step["kind"] == "final":
            return step["text"]

        name = step["name"]
        arguments = step["arguments"]
        if name not in TOOLS:
            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": f"error: unknown tool {name!r}",
                }
            )
            continue

        result = TOOLS[name](**arguments)
        messages.append({"role": "tool", "name": name, "content": str(result)})

    return "Stopped: max_steps exceeded."


def main() -> None:
    q = "What is 24 * 17? Use the multiply tool if available."
    print(run_agent(q))


if __name__ == "__main__":
    main()
