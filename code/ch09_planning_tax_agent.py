"""Chapter 9 — Plan first, then execute (tax planning).

Phase 0: OpenAI JSON extract only for session facts (income, kids, tax year, goals).
Phase A: JSON plan. Phase B: stub tools. Not tax advice."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from typing import Any

from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

CHAT_MODEL = "gpt-4o-mini"

DEFAULT_USER = (
    "I made $220k, married, 2 kids, and want to reduce taxes next year. "
    "Help me think through a baseline and what to explore next."
)


def retrieve_tax_rules(topic: str) -> str:
    """Stub RAG: canned snippets for demo (not authoritative)."""
    t = topic.lower()
    if "401" in t or "retirement" in t:
        return (
            "[stub retrieve] Pre-tax 401(k) contributions generally reduce taxable wages for federal income tax. "
            "Limits and rules depend on year and plan; verify with IRS and your plan administrator."
        )
    if "roth" in t or "traditional" in t:
        return (
            "[stub retrieve] Traditional vs Roth: traditional often defers tax on contribution; "
            "Roth uses after-tax dollars with qualified distributions potentially tax-free. "
            "Tradeoffs depend on brackets and horizon—verify with a professional."
        )
    if "standard" in t or "deduction" in t or "itemiz" in t:
        return (
            "[stub retrieve] Most filers take the standard deduction; itemizing helps when "
            "deductible expenses exceed the standard amount for that tax year. Use official IRS figures for the year."
        )
    return (
        "[stub retrieve] General: confirm filing status, dependents, and tax year before estimating. "
        "See IRS publications and Form 1040 instructions for the relevant year."
    )


def baseline_tax_placeholder(annual_income: float, married: bool, num_children: int) -> str:
    """
    Absurdly simplified placeholder — NOT real tax law.
    """
    if annual_income <= 0:
        return "error: annual_income must be positive"
    # toy brackets-ish
    rate = 0.18 if annual_income < 100_000 else 0.24 if annual_income < 200_000 else 0.32
    rough = annual_income * rate
    child_adj = min(num_children, 5) * 1_500.0
    rough = max(0.0, rough - child_adj)
    if married:
        rough *= 0.92
    return (
        f"[stub baseline] Very rough placeholder federal-style estimate ~${rough:,.0f} "
        f"(income={annual_income:,.0f}, married={married}, children={num_children}). "
        "This is NOT your real tax; use real software or a CPA."
    )


TOOLS_IMPL: dict[str, Any] = {
    "retrieve_tax_rules": retrieve_tax_rules,
    "baseline_tax_placeholder": baseline_tax_placeholder,
}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_tax_rules",
            "description": "Stub document lookup for federal individual tax topics (401k, deductions, Roth vs traditional, filing).",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "baseline_tax_placeholder",
            "description": "Placeholder baseline 'tax' estimate for demonstration only—not real tax law.",
            "parameters": {
                "type": "object",
                "properties": {
                    "annual_income": {"type": "number"},
                    "married": {"type": "boolean"},
                    "num_children": {"type": "integer", "minimum": 0, "maximum": 20},
                },
                "required": ["annual_income", "married", "num_children"],
            },
        },
    },
]


def assistant_to_message_dict(msg) -> dict[str, Any]:
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


def parse_session_facts(client: OpenAI, user_text: str) -> dict[str, Any]:
    """
    Structured session facts via OpenAI JSON only (no regex fallback).

    If the API response is not valid JSON, returns null fields plus extract_error.
    """
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
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    )
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return _empty_session_facts(f"invalid_json_from_model: {e}")

    out: dict[str, Any] = {
        "annual_income_usd": data.get("annual_income_usd"),
        "married": data.get("married"),
        "num_children": data.get("num_children"),
        "tax_year_focus_for_discussion": data.get("tax_year_focus_for_discussion"),
        "user_stated_goals": (data.get("user_stated_goals") or "")[:500],
        "confidence": data.get("confidence") or "medium",
        "source": "openai_json_extract",
    }
    return out


def run_planning_phase(
    client: OpenAI,
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
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    raw = (r.choices[0].message.content or "{}").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "steps": ["Parse user goals", "List missing facts", "Retrieve rules", "Baseline then scenarios"],
            "missing_information": ["Could not parse planner JSON"],
            "rationale": raw[:200],
        }


def run_execution_phase(
    client: OpenAI,
    user_text: str,
    plan: dict[str, Any] | None,
    session_facts: dict[str, Any],
    max_steps: int = 12,
) -> str:
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
        "Tools: retrieve_tax_rules before specific rule claims; baseline_tax_placeholder is toy math only—disclaim it.\n"
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

    for _ in range(max_steps):
        completion = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=messages,
            tools=TOOLS_SPEC,
            tool_choice="auto",
        )
        msg = completion.choices[0].message
        messages.append(assistant_to_message_dict(msg))

        if not msg.tool_calls:
            return (msg.content or "").strip()

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
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})

    return "Stopped: max_steps exceeded."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default=None, help="user message")
    parser.add_argument("--no-plan", action="store_true", help="skip planning phase (compare behavior)")
    args = parser.parse_args()

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    user_text = (args.query or DEFAULT_USER).strip()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("=== Phase 0: Session facts (OpenAI JSON extract) ===\n")
    facts = parse_session_facts(client, user_text)
    print(json.dumps(facts, ensure_ascii=False, indent=2))

    plan = None
    if not args.no_plan:
        print("\n=== Phase A: Planning (JSON) ===\n")
        plan = run_planning_phase(client, user_text, session_facts=facts)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("\n=== Phase B: Execution (tools) ===\n")
    else:
        print("\n=== Execution (tools, no plan) ===\n")

    answer = run_execution_phase(client, user_text, plan, session_facts=facts)
    print(answer)


if __name__ == "__main__":
    main()
