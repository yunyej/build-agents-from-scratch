"""Chapter 17 - Latency / cost patterns: cache, tiny router, parallel calls.

Educational only - same model (gpt-4o-mini) used for router and worker to keep cost low.

Run: python ch17_latency_cost_demo.py list
     python ch17_latency_cost_demo.py run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

from openai import AsyncOpenAI, OpenAI

from ch12_specialized_agents_demo import run_specialized_agent_with_client

from common import OPENAI_KEY_HINT, load_env

CHAT_MODEL = "gpt-4o-mini"

# In-process cache: (agent, query) -> assistant text
_RESPONSE_CACHE: dict[tuple[str, str], str] = {}


def cached_specialized(agent: str, query: str) -> tuple[str, bool]:
    key = (agent, query.strip())
    if key in _RESPONSE_CACHE:
        return _RESPONSE_CACHE[key], True
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    text = run_specialized_agent_with_client(client, agent, query)
    _RESPONSE_CACHE[key] = text
    return text, False


def route_complexity(client: OpenAI, user_text: str) -> str:
    """Cheap routing call - few tokens."""
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        max_tokens=30,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": 'Classify the user task. Output JSON only: {"level":"simple"|"complex"}. '
                "simple = one fact or file read; complex = multi-step or report.",
            },
            {"role": "user", "content": user_text[:4000]},
        ],
    )
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        return str(json.loads(raw).get("level") or "simple").lower()
    except json.JSONDecodeError:
        return "simple"


async def parallel_summaries(client: AsyncOpenAI, a: str, b: str) -> tuple[str, str]:
    async def one(label: str, text: str) -> str:
        r = await client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            max_tokens=60,
            messages=[
                {"role": "system", "content": f"One sentence summary for part {label}."},
                {"role": "user", "content": text[:2000]},
            ],
        )
        return (r.choices[0].message.content or "").strip()

    return await asyncio.gather(one("A", a), one("B", b))


def cmd_list() -> None:
    print("Chapter 17 - Latency and cost (demos)\n")
    print("1) Response cache - second identical Ch12 agent+query skips LLM.")
    print("2) Router - small max_tokens JSON classify before optional heavy path.")
    print("3) Parallel - asyncio.gather two short completions.")
    print("\nrun: runs demos with timing (needs OPENAI_API_KEY).")


async def _run_async() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)
    key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=key)
    q = "Say what 401k stub doc says in one sentence."
    agent = "document"

    t0 = time.perf_counter()
    _, hit1 = cached_specialized(agent, q)
    t1 = time.perf_counter()
    _, hit2 = cached_specialized(agent, q)
    t2 = time.perf_counter()
    print(f"cache_demo first_call_s={t1-t0:.2f} hit={hit1} second_call_s={t2-t1:.2f} hit={hit2}")

    t0 = time.perf_counter()
    lvl = route_complexity(client, q)
    print(f"router_demo level={lvl!r} latency_s={time.perf_counter()-t0:.2f}")

    ac = AsyncOpenAI(api_key=key)
    t0 = time.perf_counter()
    s1, s2 = await parallel_summaries(
        ac,
        "Topic: standard deduction (one line).",
        "Topic: 401k deferrals (one line).",
    )
    print(f"parallel_demo latency_s={time.perf_counter()-t0:.2f}")
    print(f"  partA: {s1[:120]}...")
    print(f"  partB: {s2[:120]}...")


def cmd_run() -> None:
    asyncio.run(_run_async())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", nargs="?", choices=["list", "run"], default="list")
    args = p.parse_args()
    if args.cmd == "list":
        cmd_list()
        return
    cmd_run()


if __name__ == "__main__":
    main()
