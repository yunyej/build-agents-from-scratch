"""OpenAI phases: session facts, plan, tool execution with trace, reflection."""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any, Callable, TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from tax_calculator_demo.tools import TOOLS_IMPL, TOOLS_SPEC

T = TypeVar("T")
_LOG = logging.getLogger(__name__)


def _is_retryable_exc(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        return code in (408, 429, 500, 502, 503, 504)
    return False


def _with_retries(label: str, fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    delays = (0.5, 1.5, 3.0)
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if not _is_retryable_exc(e) or attempt + 1 >= max_attempts:
                raise
            wait = delays[min(attempt, len(delays) - 1)]
            _LOG.warning("%s retry %s/%s after %ss: %s", label, attempt + 1, max_attempts, wait, e)
            time.sleep(wait)
    assert last is not None
    raise last


def assistant_to_message_dict(msg: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return out


def _empty_session_facts(extract_error: str) -> dict[str, Any]:
    return {
        "annual_income_usd": None,
        "married": None,
        "num_children": None,
        "tax_year_focus_for_discussion": None,
        "user_stated_goals": "",
        "confidence": "low",
        "source": "openai_json_extract",
        "extract_error": extract_error,
    }


def parse_session_facts(client: OpenAI, model: str, user_text: str) -> dict[str, Any]:
    y = date.today().year
    today = date.today().isoformat()
    system = (
        f"You extract structured session facts from the user's message for a tax planning assistant.\n"
        f"Today's date is {today} (calendar year {y}). Use this to interpret phrases like "
        f'"this year" vs "next year" (e.g. "next year" often means tax year {y + 1} for planning).\n\n'
        "Output ONLY valid JSON with exactly these keys:\n"
        "- annual_income_usd: number or null (full US dollars)\n"
        "- married: boolean or null (true if they indicate a married couple; false if clearly single; null if unknown)\n"
        "- num_children: integer or null (kids/dependents they mentioned)\n"
        "- tax_year_focus_for_discussion: integer or null (which tax year they care about for rules/estimates)\n"
        '- user_stated_goals: string (short summary of what they want, e.g. "reduce taxes next year")\n'
        '- confidence: string, one of "high", "medium", "low"\n\n'
        "Income normalization examples (map to annual_income_usd):\n"
        '- "$220k", "$220K", "220K", "220k", "about 220 thousand" → 220000\n'
        '- "$220,000" → 220000\n\n'
        "Rules: Do not invent income or children. If the user did not state a value, use null. "
        "For tax_year_focus_for_discussion, prefer a single year; use null if truly ambiguous."
    )

    def call():
        return client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
        )

    r = _with_retries("parse_session_facts", call)
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return _empty_session_facts(f"invalid_json_from_model: {e}")

    return {
        "annual_income_usd": data.get("annual_income_usd"),
        "married": data.get("married"),
        "num_children": data.get("num_children"),
        "tax_year_focus_for_discussion": data.get("tax_year_focus_for_discussion"),
        "user_stated_goals": (data.get("user_stated_goals") or "")[:500],
        "confidence": data.get("confidence") or "medium",
        "source": "openai_json_extract",
    }


def run_planning_phase(
    client: OpenAI,
    model: str,
    user_text: str,
    session_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system = (
        "You are a planning module for a personal tax and financial planning assistant. "
        "Output ONLY valid JSON with keys: "
        'steps (array of strings, ordered), missing_information (array of strings), '
        'rationale (short string). '
        "Steps should mirror a sensible workflow: gather facts, retrieve rules for the tax year, "
        "baseline estimate, scenario comparisons (401k, Roth vs traditional, standard vs itemized), "
        "compare, summarize. "
        "If income or tax year is unclear, list that under missing_information."
    )
    user_content = user_text
    if session_facts:
        user_content = (
            "[SESSION_FACTS_FROM_EXTRACTOR]\n"
            + json.dumps(session_facts, ensure_ascii=False, indent=2)
            + "\n\n---\n\nUSER_MESSAGE:\n"
            + user_text
        )

    def call():
        return client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        )

    r = _with_retries("run_planning_phase", call)
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "steps": ["Parse user goals", "List missing facts", "Retrieve rules", "Baseline then scenarios"],
            "missing_information": ["Could not parse planner JSON"],
            "rationale": raw[:200],
        }


def run_execution_phase_with_trace(
    client: OpenAI,
    model: str,
    user_text: str,
    plan: dict[str, Any] | None,
    session_facts: dict[str, Any],
    max_steps: int = 12,
) -> tuple[str, list[dict[str, Any]], int]:
    plan_blob = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "(no structured plan; answer directly)"
    facts_json = json.dumps(session_facts, ensure_ascii=False, indent=2)

    system = (
        "You execute a tax *planning discussion* for education. "
        "Follow the approved plan when present.\n\n"
        "CRITICAL — [PARSED_SESSION_FACTS] is authoritative for this turn:\n"
        "- If annual_income_usd is a number, do NOT ask the user for income again.\n"
        "- If num_children is a number, use it for baseline_tax_placeholder (do not ask how many kids).\n"
        "- If married is true, pass married=true to baseline_tax_placeholder; if false, pass false; if null, ask once or assume false only if user said single.\n"
        "- Use tax_year_focus_for_discussion when you mention which year's rules; do not stall waiting for tax year "
        "unless annual_income_usd and num_children are both null.\n"
        "- Your first substantive actions should be: retrieve_tax_rules for relevant topics, then "
        "baseline_tax_placeholder with the parsed numbers.\n\n"
        "Tools: retrieve_tax_rules returns passages from the federal corpus when the index is built; cite source lines "
        "from that output. baseline_tax_placeholder is toy math only—disclaim it.\n"
        "If the user asks a 'what if' scenario (e.g. extra 401(k) contribution), say honestly what the tools can "
        "and cannot compute; do not invent a second baseline number unless you clearly label it as illustrative.\n"
        "End with a short summary and CPA / tax software caveat.\n\n"
        f"APPROVED_PLAN_JSON:\n{plan_blob}"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"[PARSED_SESSION_FACTS]\n{facts_json}\n\n"
                f"---\n\nOriginal user message:\n{user_text}"
            ),
        },
    ]
    tool_trace: list[dict[str, Any]] = []
    execution_llm_rounds = 0

    for _ in range(max_steps):
        execution_llm_rounds += 1

        def call():
            return client.chat.completions.create(
                model=model,
                temperature=0,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
            )

        completion = _with_retries("execution_step", call)
        msg = completion.choices[0].message
        messages.append(assistant_to_message_dict(msg))

        if not msg.tool_calls:
            return (msg.content or "").strip(), tool_trace, execution_llm_rounds

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name not in TOOLS_IMPL:
                out = f"error: unknown tool {name!r}"
            else:
                try:
                    out = str(TOOLS_IMPL[name](**args))
                except TypeError as e:
                    out = f"error: bad arguments for {name!r}: {e}"
            tool_trace.append(
                {
                    "tool_name": name,
                    "arguments": args,
                    "output": out,
                }
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})

    return "Stopped: max_steps exceeded.", tool_trace, execution_llm_rounds


def run_reflection_phase(
    client: OpenAI,
    model: str,
    user_text: str,
    session_facts: dict[str, Any],
    plan: dict[str, Any] | None,
    tool_trace: list[dict[str, Any]],
    draft_answer: str,
) -> dict[str, Any]:
    plan_blob = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "null"
    facts_json = json.dumps(session_facts, ensure_ascii=False, indent=2)
    trace_text = json.dumps(tool_trace, ensure_ascii=False, indent=2)

    system = (
        "You are a critique/reflection module for a tax *education* assistant (not tax advice).\n"
        "You receive: the user message, parsed session facts, the plan JSON, a list of tool calls with outputs, "
        "and the assistant's draft final answer.\n\n"
        "Check three things (from the product spec):\n"
        "1) Evidence: Are concrete rule claims grounded in retrieve_tax_rules outputs, or clearly general education?\n"
        "2) Tool honesty: If the draft cites specific dollar amounts or claims a scenario was 'computed', do those "
        "numbers or scenarios appear in baseline_tax_placeholder / retrieve outputs? Flag invented savings or "
        "wrong filing status/year vs facts.\n"
        "3) Completeness: Does the draft address what the user asked (e.g. both baseline and 'what if' angles if they asked)?\n\n"
        "Output ONLY valid JSON with exactly these keys:\n"
        '- evidence_aligned: boolean\n'
        '- evidence_notes: string (short)\n'
        '- tool_outputs_match_answer: boolean\n'
        '- tool_notes: string (short)\n'
        '- completeness_for_user_goals: boolean\n'
        '- completeness_notes: string (short)\n'
        '- issues_found: array of strings (empty if none)\n'
        '- final_answer: string — the answer to show the user; if issues_found is non-empty, revise the draft to fix '
        "or explicitly disclaim each issue (still educational tone, stub-tool caveats).\n"
    )
    user_block = (
        f"USER_MESSAGE:\n{user_text}\n\n"
        f"SESSION_FACTS_JSON:\n{facts_json}\n\n"
        f"PLAN_JSON:\n{plan_blob}\n\n"
        f"TOOL_TRACE (name, arguments, output for each call):\n{trace_text}\n\n"
        f"DRAFT_FINAL_ANSWER:\n{draft_answer}"
    )

    def call():
        return client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_block},
            ],
        )

    r = _with_retries("run_reflection_phase", call)
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            "evidence_aligned": None,
            "evidence_notes": "",
            "tool_outputs_match_answer": None,
            "tool_notes": "",
            "completeness_for_user_goals": None,
            "completeness_notes": "",
            "issues_found": [f"reflection_parse_error: {e}"],
            "final_answer": draft_answer,
        }

    issues = data.get("issues_found")
    if not isinstance(issues, list):
        issues = []
    issues = [str(x) for x in issues]

    final = data.get("final_answer")
    if not isinstance(final, str) or not final.strip():
        final = draft_answer

    return {
        "evidence_aligned": data.get("evidence_aligned"),
        "evidence_notes": (data.get("evidence_notes") or "")[:2000],
        "tool_outputs_match_answer": data.get("tool_outputs_match_answer"),
        "tool_notes": (data.get("tool_notes") or "")[:2000],
        "completeness_for_user_goals": data.get("completeness_for_user_goals"),
        "completeness_notes": (data.get("completeness_notes") or "")[:2000],
        "issues_found": issues,
        "final_answer": final.strip(),
    }
