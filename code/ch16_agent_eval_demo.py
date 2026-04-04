"""Chapter 16 - Repeatable mini-benchmark for a specialist agent (Ch12).

Measures: pass/fail vs simple checks, wall latency per task, aggregate stats.
Cost estimate uses rough USD per 1M input tokens for gpt-4o-mini (adjust as needed).

Run: python ch16_agent_eval_demo.py list
     python ch16_agent_eval_demo.py run
     python ch16_agent_eval_demo.py run --agent research
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

from ch12_specialized_agents_demo import run_specialized_agent

from common import OPENAI_KEY_HINT, load_env


@dataclass
class TaskResult:
    task_id: str
    agent: str
    ok: bool
    seconds: float
    detail: str


DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "id": "r1",
        "agent": "research",
        "query": "Use stub search for carbon and list one fake URL.",
        "must_contain": "stub",
    },
    {
        "id": "d1",
        "agent": "document",
        "query": "Use lookup on deductions and write one sentence.",
        "must_contain": "deduction",
    },
    {
        "id": "c1",
        "agent": "coding",
        "query": "Read common.py and say in one line what load_env does.",
        "must_contain": "load_env",
    },
]


def run_one(task: dict[str, Any]) -> TaskResult:
    t0 = time.perf_counter()
    try:
        out = run_specialized_agent(task["agent"], task["query"], max_steps=8)
    except Exception as e:
        return TaskResult(
            task["id"],
            task["agent"],
            False,
            time.perf_counter() - t0,
            str(e),
        )
    elapsed = time.perf_counter() - t0
    needle = task.get("must_contain", "")
    ok = needle.lower() in out.lower() if needle else len(out) > 10
    return TaskResult(task["id"], task["agent"], ok, elapsed, "substring check" if ok else f"missing {needle!r}")


def cmd_list() -> None:
    print("Chapter 16 - Evaluation harness (tiny task set)\n")
    for t in DEFAULT_TASKS:
        print(f"  {t['id']}: agent={t['agent']} must_contain={t.get('must_contain')!r}")
    print("\nrun: executes each task, prints JSON summary + pass rate.")


def cmd_run(agent_filter: str | None) -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)
    tasks = [t for t in DEFAULT_TASKS if not agent_filter or t["agent"] == agent_filter]
    results = [run_one(t) for t in tasks]
    passed = sum(1 for r in results if r.ok)
    total_s = sum(r.seconds for r in results)
    report = {
        "tasks_run": len(results),
        "passed": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "total_seconds": round(total_s, 3),
        "avg_seconds": round(total_s / len(results), 3) if results else 0.0,
        "rough_cost_note_usd": "very approximate; use provider usage for truth",
        "results": [asdict(r) for r in results],
    }
    print(json.dumps(report, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", nargs="?", choices=["list", "run"], default="list")
    p.add_argument("--agent", default=None, help="only tasks for this Ch12 agent")
    args = p.parse_args()
    if args.cmd == "list":
        cmd_list()
        return
    cmd_run(args.agent)


if __name__ == "__main__":
    main()
