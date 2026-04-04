"""
Step 5 — Live demos: max iterations, invalid tools, timeouts, fallbacks.

No API key needed for demos 1–3. Optional OpenAI demo needs OPENAI_API_KEY in .env.

  python ch05_stop_conditions_demo.py
  python ch05_stop_conditions_demo.py --openai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

from common import OPENAI_KEY_HINT, load_env

BANNER = "\n" + "=" * 60


# --- Demo 1: max iterations + fallback (stub model, no network) -----------------


def multiply(a: int, b: int) -> int:
    return a * b


TOOLS: dict[str, Any] = {"multiply": multiply}


def demo_max_iterations(max_steps: int = 4) -> None:
    """
    Stub "model" always requests another tool call (pathological but common in bugs).
    Real safeguard: cap iterations and return a fallback instead of hanging the process.
    """
    print(f"{BANNER}\nDemo 1 - max iterations + fallback (no LLM)\n{BANNER}")
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "What is 6 * 7? (stub will ignore answers and keep calling tools)"}
    ]
    tool_round = 0

    for i in range(max_steps):
        # Pathological assistant: always one tool call, never a final answer.
        fake_id = f"call_{i}"
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": fake_id,
                        "type": "function",
                        "function": {
                            "name": "multiply",
                            "arguments": json.dumps({"a": 6, "b": 7}),
                        },
                    }
                ],
            }
        )
        tool_round += 1
        args = json.loads(messages[-1]["tool_calls"][0]["function"]["arguments"])
        name = messages[-1]["tool_calls"][0]["function"]["name"]
        if name not in TOOLS:
            out = f"error: unknown tool {name!r}"
        else:
            out = str(TOOLS[name](**args))
        messages.append({"role": "tool", "tool_call_id": fake_id, "content": out})
        print(f"  Round {tool_round}: tool multiply -> {out}")

    fallback = (
        f"FALLBACK: Stopped after {max_steps} tool rounds (max_steps safeguard). "
        "The real assistant never produced a final message; without a cap this could run forever."
    )
    print(f"\n  >>> {fallback}\n")


# --- Demo 2: invalid tool name ---------------------------------------------------


def demo_invalid_tool() -> None:
    print(f"{BANNER}\nDemo 2 - invalid / unknown tool handling\n{BANNER}")
    requested = "delete_everything"
    args = {"confirm": True}
    if requested not in TOOLS:
        msg = f"error: unknown tool {requested!r}"
    else:
        msg = str(TOOLS[requested](**args))
    print(f"  Model asked for: {requested}({args})")
    print(f"  Tool layer returns to the model: {msg!r}")
    print(
        "  (Your loop appends this as tool output; the model can recover or you can abort.)\n"
    )


# --- Demo 3: HTTP timeout --------------------------------------------------------


def demo_timeout() -> None:
    print(f"{BANNER}\nDemo 3 - timeout handling (Open-Meteo geocoding)\n{BANNER}")
    url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        with httpx.Client(timeout=0.001) as client:
            client.get(url, params={"name": "Paris", "count": 1})
    except httpx.TimeoutException as e:
        observation = f"error: request timed out ({e!r})"
    except httpx.HTTPError as e:
        observation = f"error: HTTP failure ({e!r})"
    else:
        observation = "unexpected: request succeeded (try a smaller timeout)"

    print(f"  Timeout set to 0.001s on purpose.")
    print(f"  String you might return to the model as tool output: {observation!r}\n")


# --- Demo 4: optional OpenAI — same loop as ch04, verbose + tight max_steps -------


def demo_openai_limited(max_steps: int = 6) -> None:
    from openai import OpenAI

    print(f"{BANNER}\nDemo 4 - OpenAI agent with max_steps={max_steps} (verbose)\n{BANNER}")
    if not os.getenv("OPENAI_API_KEY"):
        print(f"  Skip: {OPENAI_KEY_HINT}\n")
        return

    # Minimal copy of ch04 tool spec (one tool)
    from ch04_city_coordinates_agent import TOOLS_IMPL, TOOLS_SPEC, assistant_to_message_dict

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_text = "What are the coordinates of London? One short sentence."
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Use get_city_coordinates for place coordinates; otherwise answer briefly. "
                "After tools return, reply concisely."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    for step_i in range(max_steps):
        print(f"  --- API call #{step_i + 1} ---")
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
            print(f"  Final (no tools): {msg.content!r}\n")
            return

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"  Tool: {name}({args})")
            if name not in TOOLS_IMPL:
                out = f"error: unknown tool {name!r}"
            else:
                try:
                    out = str(TOOLS_IMPL[name](**args))
                except TypeError as e:
                    out = f"error: bad arguments: {e}"
            print(f"  Observation: {out[:200]}{'...' if len(out) > 200 else ''}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})

    print(
        f"  FALLBACK: max_steps={max_steps} exceeded without a final answer.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 5 safeguard demos")
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Also run the OpenAI demo (needs OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    load_env()

    demo_max_iterations(max_steps=4)
    demo_invalid_tool()
    demo_timeout()

    if args.openai:
        demo_openai_limited(max_steps=6)
    else:
        print(
            f"{BANNER}\nDemo 4 skipped (add --openai to run with your API key)\n{BANNER}\n"
        )


if __name__ == "__main__":
    main()
