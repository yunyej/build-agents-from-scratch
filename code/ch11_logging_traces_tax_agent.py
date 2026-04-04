"""Chapter 11 — Persist agent traces to SQLite (local) with a normalized schema.

Reuses the Chapter 10 pipeline (facts → plan → execution + tool trace → reflection),
then writes several tables so you can inspect runs, tools, and stub "retrieval" rows.

Cloud note: the same logical tables map well to Postgres + blob store for large payloads;
see ../11-logging-and-traces.md.

Not tax advice. Stub tools only."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from ch10_reflection_tax_agent import (
    CHAT_MODEL,
    DEFAULT_USER,
    parse_session_facts,
    run_execution_phase_with_trace,
    run_planning_phase,
    run_reflection_phase,
)
from common import OPENAI_KEY_HINT, load_env

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "ch11_agent_traces.sqlite"


def connect_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            user_message TEXT NOT NULL,
            chat_model TEXT NOT NULL,
            no_plan INTEGER NOT NULL DEFAULT 0,
            no_reflect INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_summary TEXT,
            execution_llm_rounds INTEGER,
            max_execution_steps INTEGER NOT NULL DEFAULT 12,
            tool_call_count INTEGER NOT NULL DEFAULT 0,
            draft_answer TEXT,
            final_answer TEXT
        );

        CREATE TABLE IF NOT EXISTS session_facts (
            run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
            facts_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plans (
            run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
            plan_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            output_text TEXT NOT NULL,
            UNIQUE (run_id, seq)
        );

        /* Stub RAG: one row per retrieve_tax_rules call (topic + snippet). In production:
           add source_id, chunk_id, embedding_version, filter_year, etc. */
        CREATE TABLE IF NOT EXISTS retrieval_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            query_topic TEXT NOT NULL,
            retrieved_snippet TEXT NOT NULL,
            source_id TEXT,
            UNIQUE (run_id, seq)
        );

        CREATE TABLE IF NOT EXISTS reflections (
            run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
            reflection_json TEXT NOT NULL,
            draft_answer TEXT NOT NULL,
            final_answer TEXT NOT NULL
        );
        """
    )
    conn.commit()


def persist_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    user_message: str,
    no_plan: bool,
    no_reflect: bool,
    status: str,
    error_summary: str | None,
    session_facts: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    draft_answer: str | None,
    tool_trace: list[dict[str, Any]],
    execution_llm_rounds: int | None,
    max_execution_steps: int,
    reflection: dict[str, Any] | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    tool_call_count = len(tool_trace)
    final_ans: str | None = None
    if draft_answer is not None:
        if reflection is not None:
            final_ans = str(reflection.get("final_answer") or draft_answer)
        else:
            final_ans = draft_answer
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO runs (
            run_id, created_at, user_message, chat_model, no_plan, no_reflect,
            status, error_summary, execution_llm_rounds, max_execution_steps, tool_call_count,
            draft_answer, final_answer
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            user_message,
            CHAT_MODEL,
            1 if no_plan else 0,
            1 if no_reflect else 0,
            status,
            error_summary,
            execution_llm_rounds,
            max_execution_steps,
            tool_call_count,
            draft_answer,
            final_ans,
        ),
    )
    if session_facts is not None:
        cur.execute(
            "INSERT INTO session_facts (run_id, facts_json) VALUES (?, ?)",
            (run_id, json.dumps(session_facts, ensure_ascii=False)),
        )
    if plan is not None:
        cur.execute(
            "INSERT INTO plans (run_id, plan_json) VALUES (?, ?)",
            (run_id, json.dumps(plan, ensure_ascii=False)),
        )
    retrieval_seq = 0
    for seq, row in enumerate(tool_trace):
        name = row.get("tool_name") or ""
        args = row.get("arguments") if isinstance(row.get("arguments"), dict) else {}
        out = row.get("output") or ""
        cur.execute(
            """
            INSERT INTO tool_calls (run_id, seq, tool_name, arguments_json, output_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, seq, name, json.dumps(args, ensure_ascii=False), out),
        )
        if name == "retrieve_tax_rules":
            topic = str(args.get("topic") or "")
            cur.execute(
                """
                INSERT INTO retrieval_events (run_id, seq, query_topic, retrieved_snippet, source_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, retrieval_seq, topic, out, None),
            )
            retrieval_seq += 1

    if reflection is not None and draft_answer is not None:
        cur.execute(
            """
            INSERT INTO reflections (run_id, reflection_json, draft_answer, final_answer)
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                json.dumps(reflection, ensure_ascii=False),
                draft_answer,
                final_ans or draft_answer,
            ),
        )
    conn.commit()


def cmd_list(conn: sqlite3.Connection, limit: int) -> None:
    rows = conn.execute(
        """
        SELECT run_id, created_at, status, user_message, tool_call_count, execution_llm_rounds
        FROM runs ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if not rows:
        print("No runs in database.")
        return
    for r in rows:
        msg = (r["user_message"] or "")[:72]
        print(
            f"{r['run_id']}\t{r['created_at']}\t{r['status']}\t"
            f"tools={r['tool_call_count']}\trounds={r['execution_llm_rounds']}\t{msg!r}"
        )


def cmd_show(conn: sqlite3.Connection, run_id: str) -> None:
    run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not run:
        print(f"No run {run_id!r}", file=sys.stderr)
        sys.exit(1)
    out: dict[str, Any] = {k: run[k] for k in run.keys()}
    sf = conn.execute("SELECT facts_json FROM session_facts WHERE run_id = ?", (run_id,)).fetchone()
    out["session_facts"] = json.loads(sf["facts_json"]) if sf else None
    pl = conn.execute("SELECT plan_json FROM plans WHERE run_id = ?", (run_id,)).fetchone()
    out["plan"] = json.loads(pl["plan_json"]) if pl else None
    tools = conn.execute(
        "SELECT seq, tool_name, arguments_json, output_text FROM tool_calls WHERE run_id = ? ORDER BY seq",
        (run_id,),
    ).fetchall()
    out["tool_calls"] = [
        {
            "seq": t["seq"],
            "tool_name": t["tool_name"],
            "arguments": json.loads(t["arguments_json"]),
            "output": t["output_text"],
        }
        for t in tools
    ]
    retr = conn.execute(
        "SELECT seq, query_topic, retrieved_snippet, source_id FROM retrieval_events WHERE run_id = ? ORDER BY seq",
        (run_id,),
    ).fetchall()
    out["retrieval_events"] = [dict(r) for r in retr]
    ref = conn.execute("SELECT * FROM reflections WHERE run_id = ?", (run_id,)).fetchone()
    if ref:
        out["reflection"] = {
            "draft_answer": ref["draft_answer"],
            "final_answer": ref["final_answer"],
            "reflection_json": json.loads(ref["reflection_json"]),
        }
    else:
        out["reflection"] = None
    print(json.dumps(out, ensure_ascii=False, indent=2))


def run_agent_and_persist(
    client: OpenAI,
    user_text: str,
    *,
    no_plan: bool,
    no_reflect: bool,
    db_path: Path,
    max_execution_steps: int = 12,
) -> tuple[str, str | None]:
    run_id = uuid.uuid4().hex
    facts: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    draft: str | None = None
    trace: list[dict[str, Any]] = []
    rounds: int | None = None
    reflection: dict[str, Any] | None = None
    status = "ok"
    err: str | None = None
    answer_out: str | None = None

    conn = connect_db(db_path)
    init_schema(conn)
    try:
        facts = parse_session_facts(client, user_text)
        if not no_plan:
            plan = run_planning_phase(client, user_text, session_facts=facts)
        draft, trace, rounds = run_execution_phase_with_trace(
            client, user_text, plan, session_facts=facts, max_steps=max_execution_steps
        )
        if not no_reflect:
            reflection = run_reflection_phase(client, user_text, facts, plan, trace, draft)
            answer_out = str(reflection.get("final_answer") or draft).strip() or draft
        else:
            answer_out = (draft or "").strip() or None
    except Exception as e:
        status = "error"
        err = f"{type(e).__name__}: {e}"
    finally:
        persist_run(
            conn,
            run_id=run_id,
            user_message=user_text,
            no_plan=no_plan,
            no_reflect=no_reflect,
            status=status,
            error_summary=err,
            session_facts=facts,
            plan=plan,
            draft_answer=draft,
            tool_trace=trace,
            execution_llm_rounds=rounds,
            max_execution_steps=max_execution_steps,
            reflection=reflection if not no_reflect else None,
        )
        conn.close()

    if status != "ok":
        print(err, file=sys.stderr)
        sys.exit(1)

    return run_id, answer_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Ch11: tax demo agent + SQLite trace store")
    parser.add_argument("query", nargs="?", default=None, help="user message")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--no-plan", action="store_true")
    parser.add_argument("--no-reflect", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_runs", help="list recent runs and exit")
    parser.add_argument("--show", metavar="RUN_ID", help="print JSON for one run and exit")
    parser.add_argument("--list-limit", type=int, default=20)
    args = parser.parse_args()

    load_env()
    db_path = args.db.resolve()

    if args.list_runs:
        conn = connect_db(db_path)
        init_schema(conn)
        cmd_list(conn, args.list_limit)
        conn.close()
        return

    if args.show:
        conn = connect_db(db_path)
        init_schema(conn)
        cmd_show(conn, args.show.strip())
        conn.close()
        return

    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    user_text = (args.query or DEFAULT_USER).strip()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("=== Running pipeline (same as Ch 10) + persisting trace ===\n")
    run_id, answer = run_agent_and_persist(
        client,
        user_text,
        no_plan=args.no_plan,
        no_reflect=args.no_reflect,
        db_path=db_path,
    )
    if answer:
        print("\n--- Final answer ---\n")
        print(answer)
    print(f"\nSaved run_id={run_id}")
    print(f"Database: {db_path}")
    print("\nInspect:")
    print(f'  python ch11_logging_traces_tax_agent.py --db "{db_path}" --show {run_id}')


if __name__ == "__main__":
    main()
