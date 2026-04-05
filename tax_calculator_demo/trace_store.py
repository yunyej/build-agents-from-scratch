"""SQLite trace persistence (Chapter 11–style schema)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    chat_model: str,
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
            chat_model,
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


def list_runs(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT run_id, created_at, status, user_message, tool_call_count, execution_llm_rounds
        FROM runs ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def fetch_run_json(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not run:
        return None
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
    return out


def new_run_id() -> str:
    return uuid.uuid4().hex
