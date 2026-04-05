"""Orchestrates the full pipeline and optional trace persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from tax_calculator_demo import tools as tools_mod
from tax_calculator_demo.config import Settings
from tax_calculator_demo.llm_pipeline import (
    parse_session_facts,
    run_execution_phase_with_trace,
    run_planning_phase,
    run_reflection_phase,
)
from tax_calculator_demo.trace_store import connect_db, init_schema, new_run_id, persist_run

_LOG = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    run_id: str
    status: str
    error_summary: str | None
    user_message: str
    session_facts: dict[str, Any] | None
    plan: dict[str, Any] | None
    draft_answer: str | None
    tool_trace: list[dict[str, Any]]
    execution_llm_rounds: int | None
    reflection: dict[str, Any] | None
    final_answer: str | None

    @property
    def success(self) -> bool:
        return self.status == "ok"


class TaxPlanningAgentService:
    """
    End-to-end agent: extract facts → plan → execute (tools) → reflect → persist trace.

    Retrieval targets `rag_federal_individual` when `data/index` is present.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )
        tools_mod.configure_rag(self._client, settings)

    def run(
        self,
        user_message: str,
        *,
        skip_plan: bool = False,
        skip_reflect: bool = False,
        persist_trace: bool = True,
    ) -> AgentRunResult:
        if not (self._settings.openai_api_key or "").strip():
            raise ValueError("OPENAI_API_KEY is not set (required for run).")
        tools_mod.configure_rag(self._client, self._settings)
        run_id = new_run_id()
        facts: dict[str, Any] | None = None
        plan: dict[str, Any] | None = None
        draft: str | None = None
        trace: list[dict[str, Any]] = []
        rounds: int | None = None
        reflection: dict[str, Any] | None = None
        status = "ok"
        err: str | None = None
        model = self._settings.openai_chat_model
        max_steps = self._settings.max_execution_steps

        try:
            facts = parse_session_facts(self._client, model, user_message)
            if not skip_plan:
                plan = run_planning_phase(self._client, model, user_message, session_facts=facts)
            draft, trace, rounds = run_execution_phase_with_trace(
                self._client,
                model,
                user_message,
                plan,
                session_facts=facts,
                max_steps=max_steps,
            )
            if not skip_reflect:
                reflection = run_reflection_phase(
                    self._client, model, user_message, facts, plan, trace, draft
                )
        except Exception as e:
            status = "error"
            err = f"{type(e).__name__}: {e}"
            _LOG.error("run_failed run_id=%s %s", run_id, err)

        final: str | None = None
        if status == "ok" and draft:
            if reflection is not None:
                final = str(reflection.get("final_answer") or draft).strip() or draft
            else:
                final = draft.strip() or draft

        if persist_trace:
            db_path = self._settings.resolved_trace_db()
            conn = connect_db(db_path)
            try:
                init_schema(conn)
                persist_run(
                    conn,
                    run_id=run_id,
                    chat_model=model,
                    user_message=user_message,
                    no_plan=skip_plan,
                    no_reflect=skip_reflect,
                    status=status,
                    error_summary=err,
                    session_facts=facts,
                    plan=plan,
                    draft_answer=draft,
                    tool_trace=trace,
                    execution_llm_rounds=rounds,
                    max_execution_steps=max_steps,
                    reflection=reflection if not skip_reflect else None,
                )
            finally:
                conn.close()
            _LOG.info("trace_persisted run_id=%s db=%s", run_id, db_path)

        return AgentRunResult(
            run_id=run_id,
            status=status,
            error_summary=err,
            user_message=user_message,
            session_facts=facts,
            plan=plan,
            draft_answer=draft,
            tool_trace=trace,
            execution_llm_rounds=rounds,
            reflection=reflection,
            final_answer=final,
        )
