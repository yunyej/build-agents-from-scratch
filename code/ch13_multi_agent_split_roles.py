"""Chapter 13 — Split roles: supervisor routes, one specialist worker, then critic (no tools).

Uses Chapter 12 workers (research / document / coding) with *only* the chosen worker's tools.
Supervisor and critic are plain LLM calls — illustrates planner / executor / critic and
researcher / writer / reviewer patterns in one pipeline.

Run: python ch13_multi_agent_split_roles.py list
     python ch13_multi_agent_split_roles.py run "Your task"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from openai import OpenAI

from ch12_specialized_agents_demo import AGENTS, CHAT_MODEL, run_specialized_agent_with_client
from common import OPENAI_KEY_HINT, load_env

_SUPERVISOR_SYSTEM = """You are a supervisor that routes the user request to exactly ONE worker.

Workers (pick exactly one key):
- "research" — stub web search + citations (good for "find sources", "what do people say")
- "document" — stub doc lookup + structured report (good for "summarize topic", "explain deductions")
- "coding" — read allowlisted repo files + stub math/tests (good for "read file", "compute expression")

Output ONLY valid JSON: {"worker": "<research|document|coding>", "one_line_plan": "..."}"""


def supervisor_route(client: OpenAI, user_text: str) -> tuple[str, str]:
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SUPERVISOR_SYSTEM},
            {"role": "user", "content": user_text},
        ],
    )
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "research", "fallback: invalid supervisor JSON"
    w = (data.get("worker") or "research").strip().lower()
    if w not in AGENTS:
        w = "research"
    plan = (data.get("one_line_plan") or "")[:500]
    return w, plan


def critic_phase(client: OpenAI, user_text: str, worker_key: str, worker_output: str) -> str:
    sys = (
        "You are a critic. The user asked something; a specialized worker answered. "
        "Say in 3–5 sentences whether the answer plausibly addresses the request, "
        "and name one gap or risk. Do not call tools."
    )
    body = (
        f"USER_REQUEST:\n{user_text}\n\n"
        f"WORKER_ROLE: {worker_key}\n\n"
        f"WORKER_OUTPUT:\n{worker_output[:12000]}"
    )
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": body},
        ],
    )
    return (r.choices[0].message.content or "").strip()


def run_pipeline(user_text: str) -> dict[str, Any]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    worker, plan = supervisor_route(client, user_text)
    worker_out = run_specialized_agent_with_client(client, worker, user_text)
    critic_out = critic_phase(client, user_text, worker, worker_out)
    return {
        "supervisor_pick": worker,
        "supervisor_plan": plan,
        "worker_output": worker_out,
        "critic": critic_out,
    }


def cmd_list() -> None:
    print("Chapter 13 - Split roles (supervisor -> one worker -> critic)\n")
    print("Workers (from Ch12):", ", ".join(AGENTS.keys()))
    print("\nFlow:")
    print("  1. Supervisor (JSON): chooses worker + one-line plan -- no tools.")
    print("  2. Worker: Ch12 tool loop for that role only.")
    print("  3. Critic: reads user + worker output -- no tools.")
    print("\nExample:")
    print('  python ch13_multi_agent_split_roles.py run "Find stub sources on carbon pricing"')
    print('  python ch13_multi_agent_split_roles.py run "Summarize the 401k stub doc"')


def main() -> None:
    p = argparse.ArgumentParser(description="Ch13: supervisor + worker + critic")
    p.add_argument("cmd", nargs="?", choices=["list", "run"], default="list")
    p.add_argument("query", nargs="?", default=None)
    args = p.parse_args()

    if args.cmd == "list":
        cmd_list()
        return

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)
    q = (args.query or "Say hello and pick a worker for a tiny task.").strip()
    out = run_pipeline(q)
    print("=== Supervisor ===")
    print(f"worker={out['supervisor_pick']!r} plan={out['supervisor_plan']!r}\n")
    print("=== Worker output ===\n")
    print(out["worker_output"])
    print("\n=== Critic ===\n")
    print(out["critic"])


if __name__ == "__main__":
    main()
