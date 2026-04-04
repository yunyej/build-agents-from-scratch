"""Chapter 14 — Coordination rules: shared state, reviewer gate, optional retry, escalation flag.

Builds on Ch13 routing + Ch12 workers, adds:
- explicit shared_run_state (dict) updated each phase
- reviewer JSON: approved, notes, escalate (only reviewer + supervisor may "decide"; worker has tools only)
- if not approved and not escalate: one worker retry with reviewer notes
- tool calls are impossible for supervisor/reviewer in code (no tools= passed)

Run: python ch14_multi_agent_coordination.py list
     python ch14_multi_agent_coordination.py run "Your task"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from ch12_specialized_agents_demo import AGENTS, CHAT_MODEL, run_specialized_agent_with_client
from ch13_multi_agent_split_roles import supervisor_route
from common import OPENAI_KEY_HINT, load_env

_REVIEWER_SYSTEM = """You are the final reviewer for a multi-agent pipeline.

You receive: the user request, which worker ran, and the worker's answer.

Output ONLY valid JSON with keys:
- approved: boolean — true if the answer is good enough to show the user
- notes: string — short feedback (required if not approved)
- escalate: boolean — true if a human or different system should take over (e.g. policy risk, missing data)

Rules: Be strict but fair. Stub tools mean answers are illustrative — do not reject solely for that if the user asked for a demo task."""


def reviewer_json(client: OpenAI, user_text: str, worker_key: str, worker_output: str) -> dict[str, Any]:
    body = (
        f"USER_REQUEST:\n{user_text}\n\nWORKER: {worker_key}\n\nOUTPUT:\n{worker_output[:12000]}"
    )
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _REVIEWER_SYSTEM},
            {"role": "user", "content": body},
        ],
    )
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"approved": True, "notes": "reviewer JSON parse failed; defaulting approved", "escalate": False}
    return {
        "approved": bool(data.get("approved")),
        "notes": str(data.get("notes") or "")[:2000],
        "escalate": bool(data.get("escalate")),
    }


@dataclass
class SharedRunState:
    """Minimal shared memory passed through the run (Phase 6 / Ch14)."""

    user_request: str
    supervisor_pick: str = ""
    supervisor_plan: str = ""
    worker_attempts: list[str] = field(default_factory=list)
    reviewer_rounds: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    escalation: bool = False
    tool_user_only: str = ""  # which role had tools


def run_coordinated(user_text: str, max_retries: int = 1) -> SharedRunState:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    state = SharedRunState(user_request=user_text)

    worker, plan = supervisor_route(client, user_text)
    state.supervisor_pick = worker
    state.supervisor_plan = plan
    state.tool_user_only = worker  # only this worker's tools are invoked below

    attempt_prompt = user_text
    for attempt in range(max_retries + 1):
        w_out = run_specialized_agent_with_client(client, worker, attempt_prompt)
        state.worker_attempts.append(w_out)

        rev = reviewer_json(client, user_text, worker, w_out)
        state.reviewer_rounds.append(rev)

        if rev.get("escalate"):
            state.escalation = True
            state.final_answer = w_out
            return state
        if rev.get("approved"):
            state.final_answer = w_out
            return state
        if attempt >= max_retries:
            state.final_answer = w_out
            return state
        attempt_prompt = (
            f"{user_text}\n\n---\nReviewer requested revision (not approved). "
            f"Address this feedback:\n{rev.get('notes') or '(no notes)'}"
        )

    state.final_answer = state.worker_attempts[-1] if state.worker_attempts else ""
    return state


def cmd_list() -> None:
    print("Chapter 14 - Coordination rules (enforced in code)\n")
    print("Who may use tools:")
    print("  - Supervisor: NO tools (JSON routing only).")
    print("  - Worker (research|document|coding): ONLY that agent's Ch12 tool list.")
    print("  - Reviewer: NO tools (JSON verdict: approved, notes, escalate).")
    print("\nShared state fields: user_request, supervisor_pick, supervisor_plan,")
    print("  worker_attempts[], reviewer_rounds[], final_answer, escalation, tool_user_only")
    print("\nIf not approved and not escalate: one automatic retry with reviewer notes.")
    print("If escalate: stop; final_answer still last worker text (flag escalation for human).")
    print("\nExample:")
    print('  python ch14_multi_agent_coordination.py run "Explain 401k stub in two bullets"')


def main() -> None:
    p = argparse.ArgumentParser(description="Ch14: coordination + reviewer gate")
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
    q = (args.query or "Draft a one-paragraph stub report on deductions.").strip()
    st = run_coordinated(q)
    print("=== Run summary ===")
    print(f"worker={st.supervisor_pick!r}  tool_user_only={st.tool_user_only!r}")
    print(f"worker_attempts={len(st.worker_attempts)}  escalation={st.escalation}")
    if st.reviewer_rounds:
        last = st.reviewer_rounds[-1]
        print(f"last_review: approved={last.get('approved')} escalate={last.get('escalate')}")
    print("\n=== shared_run_state (JSON) ===\n")
    print(json.dumps(st.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
