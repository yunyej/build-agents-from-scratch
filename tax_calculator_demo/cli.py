"""CLI entry: run from repository root as `python -m tax_calculator_demo`."""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from tax_calculator_demo import __version__
from tax_calculator_demo.config import Settings
from tax_calculator_demo.logging_config import setup_logging
from tax_calculator_demo.service import TaxPlanningAgentService
from tax_calculator_demo.trace_store import connect_db, fetch_run_json, init_schema, list_runs

DEFAULT_QUERY = (
    "I made $220k, married, 2 kids, and want to reduce taxes next year. "
    "Help me think through a baseline and what to explore next."
)


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        settings = Settings()
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 2
    setup_logging(settings.log_level)
    service = TaxPlanningAgentService(settings)
    msg = (args.message or DEFAULT_QUERY).strip()
    try:
        result = service.run(
            msg,
            skip_plan=args.no_plan,
            skip_reflect=args.no_reflect,
            persist_trace=not args.no_persist,
        )
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if args.json:
        payload = {
            "run_id": result.run_id,
            "status": result.status,
            "error_summary": result.error_summary,
            "final_answer": result.final_answer,
            "draft_answer": result.draft_answer,
            "session_facts": result.session_facts,
            "plan": result.plan,
            "tool_trace": result.tool_trace,
            "execution_llm_rounds": result.execution_llm_rounds,
            "reflection": result.reflection,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if result.success else 1

    if not result.success:
        print(result.error_summary or "error", file=sys.stderr)
        return 1
    print(result.final_answer or "")
    if not args.quiet:
        hint = "not persisted (--no-persist)" if args.no_persist else f"use: show {result.run_id}"
        print(f"\n(run_id={result.run_id}, {hint})", file=sys.stderr)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    try:
        settings = Settings()
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 2
    db = settings.resolved_trace_db()
    conn = connect_db(db)
    init_schema(conn)
    rows = list_runs(conn, args.limit)
    conn.close()
    if not rows:
        print("No runs.")
        return 0
    for r in rows:
        msg = (r["user_message"] or "")[:72]
        print(
            f"{r['run_id']}\t{r['created_at']}\t{r['status']}\t"
            f"tools={r['tool_call_count']}\trounds={r['execution_llm_rounds']}\t{msg!r}"
        )
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    try:
        settings = Settings()
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 2
    db = settings.resolved_trace_db()
    conn = connect_db(db)
    init_schema(conn)
    data = fetch_run_json(conn, args.run_id.strip())
    conn.close()
    if not data:
        print(f"No run {args.run_id!r}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tax_calculator_demo",
        description="Educational tax planning agent (not tax advice). Run from repo root: python -m tax_calculator_demo",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Run the agent on a user message")
    r.add_argument("message", nargs="?", default=None, help="user message (optional)")
    r.add_argument("--no-plan", action="store_true", help="skip planning phase")
    r.add_argument("--no-reflect", action="store_true", help="skip reflection phase")
    r.add_argument("--no-persist", action="store_true", help="do not write SQLite trace")
    r.add_argument("--json", action="store_true", help="print full structured result")
    r.add_argument("--quiet", action="store_true", help="only print final answer text")
    r.set_defaults(func=_cmd_run)

    l = sub.add_parser("list-runs", help="List recent persisted runs (no OpenAI call)")
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(func=_cmd_list)

    s = sub.add_parser("show", help="Print JSON for one persisted run")
    s.add_argument("run_id", help="run id from list-runs")
    s.set_defaults(func=_cmd_show)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        print(
            "Notice: educational demo only — not tax, legal, or investment advice.\n",
            file=sys.stderr,
        )
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
