"""Chapter 12 — Three specialized agents, each with a *narrow* toolset (stubs).

Run one agent at a time so the model only sees tools that match its role.
Compare: `python ch12_specialized_agents_demo.py list` then pick a role.

Not real web search or code execution — educational stubs only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

CHAT_MODEL = "gpt-4o-mini"
_CODE_DIR = Path(__file__).resolve().parent
_ALLOWED_READ = frozenset({"common.py", "requirements.txt", "README.md"})


# --- Research tools (narrow) ---
def web_search_stub(query: str) -> str:
    """Stub: pretend search results (no network)."""
    q = query.strip().lower()
    if "climate" in q or "carbon" in q:
        return (
            "[stub search] (1) EPA overview of greenhouse gas programs — example.edu/climate-overview\n"
            "(2) IPCC summary for policymakers — example.org/ipcc-syr"
        )
    return (
        f"[stub search] No live search. Pretend top hit for {query!r}: "
        "example.org/wiki/Relevant_Topic — snippet: introductory paragraph only."
    )


def clip_source_stub(url: str, max_chars: int = 400) -> str:
    """Stub: pretend fetched excerpt."""
    mc = max(80, min(max_chars, 2000))
    return (
        f"[stub clip] URL={url!r} excerpt ({mc} chars max): "
        "This is a placeholder passage. In production you would fetch and truncate real HTML/PDF."
    )


def format_citation_stub(title: str, url: str) -> str:
    return f"- {title}. Retrieved from {url}"


# --- Coding tools (narrow) ---
def read_repo_file_stub(filename: str) -> str:
    """Read a small allowlisted file under this `code/` folder only."""
    base = Path(filename).name
    if base not in _ALLOWED_READ:
        return f"error: not allowlisted (allowed: {sorted(_ALLOWED_READ)})"
    path = _CODE_DIR / base
    if not path.is_file():
        return f"error: missing file {base!r}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:8000] + ("…" if len(text) > 8000 else "")


def eval_math_stub(expression: str) -> str:
    """Tiny safe-ish eval: digits, operators + - * / ( ), spaces only."""
    cleaned = "".join(c for c in expression if c in "0123456789+-*/(). ")
    if not cleaned or cleaned != expression.strip():
        return "error: only digits, + - * / ( ) allowed"
    try:
        return str(eval(cleaned, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"error: {e}"


def run_tests_stub(label: str) -> str:
    return f"[stub tests] suite={label!r} — passed=3 failed=0 skipped=0 (not real pytest)"


# --- Document QA tools (narrow) ---
_DOCS = {
    "deduction": (
        "Standard deduction: most filers claim a fixed deduction unless itemizing exceeds it. "
        "Itemized deductions include state taxes, mortgage interest subject to limits, and charity."
    ),
    "401k": (
        "Traditional 401(k) deferrals reduce taxable wages for federal income tax; limits vary by year. "
        "Employer plans set eligibility and match rules."
    ),
}


def lookup_passage_stub(topic: str) -> str:
    t = topic.lower()
    for key, body in _DOCS.items():
        if key in t:
            return f"[stub doc:{key}] {body}"
    return f"[stub doc] No canned passage for {topic!r}. Try topic containing 'deduction' or '401k'."


def bullets_from_text_stub(text: str, max_bullets: int = 5) -> str:
    n = max(1, min(max_bullets, 10))
    return json.dumps(
        {"bullets": [f"Point {i+1} (stub): summarize substring of input" for i in range(n)]},
        ensure_ascii=False,
    )


def structured_report_stub(title: str, body_markdown: str) -> str:
    return f"## {title}\n\n{body_markdown}\n\n---\n[stub report footer]"


# Registry: agent name -> system prompt, tool names, specs, implementations
def _spec(
    name: str,
    desc: str,
    props: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


RESEARCH_TOOLS_IMPL: dict[str, Any] = {
    "web_search_stub": web_search_stub,
    "clip_source_stub": clip_source_stub,
    "format_citation_stub": format_citation_stub,
}
RESEARCH_TOOLS_SPEC = [
    _spec("web_search_stub", "Stub web search returning fake URLs/snippets.", {"query": {"type": "string"}}, ["query"]),
    _spec(
        "clip_source_stub",
        "Stub: pretend to fetch an excerpt from a URL.",
        {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
        ["url"],
    ),
    _spec(
        "format_citation_stub",
        "Format a citation line for notes.",
        {"title": {"type": "string"}, "url": {"type": "string"}},
        ["title", "url"],
    ),
]

CODING_TOOLS_IMPL: dict[str, Any] = {
    "read_repo_file_stub": read_repo_file_stub,
    "eval_math_stub": eval_math_stub,
    "run_tests_stub": run_tests_stub,
}
CODING_TOOLS_SPEC = [
    _spec(
        "read_repo_file_stub",
        f"Read allowlisted file from this repository's `code/` folder only: {sorted(_ALLOWED_READ)}.",
        {"filename": {"type": "string"}},
        ["filename"],
    ),
    _spec(
        "eval_math_stub",
        "Evaluate a simple arithmetic expression (digits and + - * / parentheses only).",
        {"expression": {"type": "string"}},
        ["expression"],
    ),
    _spec(
        "run_tests_stub",
        "Stub test runner result string.",
        {"label": {"type": "string"}},
        ["label"],
    ),
]

DOCUMENT_TOOLS_IMPL: dict[str, Any] = {
    "lookup_passage_stub": lookup_passage_stub,
    "bullets_from_text_stub": bullets_from_text_stub,
    "structured_report_stub": structured_report_stub,
}
DOCUMENT_TOOLS_SPEC = [
    _spec(
        "lookup_passage_stub",
        "Stub document lookup by topic keyword (deduction, 401k).",
        {"topic": {"type": "string"}},
        ["topic"],
    ),
    _spec(
        "bullets_from_text_stub",
        "Stub: return JSON with bullet placeholders from input text.",
        {"text": {"type": "string"}, "max_bullets": {"type": "integer"}},
        ["text"],
    ),
    _spec(
        "structured_report_stub",
        "Stub: wrap body in a titled markdown report.",
        {"title": {"type": "string"}, "body_markdown": {"type": "string"}},
        ["title", "body_markdown"],
    ),
]

AGENTS: dict[str, dict[str, Any]] = {
    "research": {
        "system": (
            "You are a research assistant with ONLY web_search_stub, clip_source_stub, and format_citation_stub. "
            "Use search then optionally clip and cite. Do not claim live internet access — results are stubs. "
            "End with short bullet findings and a references list."
        ),
        "impl": RESEARCH_TOOLS_IMPL,
        "spec": RESEARCH_TOOLS_SPEC,
    },
    "coding": {
        "system": (
            "You are a coding assistant with ONLY read_repo_file_stub, eval_math_stub, run_tests_stub. "
            "Read allowlisted files when needed; use eval_math_stub for arithmetic checks. "
            "Do not ask for tools you do not have. Summarize briefly."
        ),
        "impl": CODING_TOOLS_IMPL,
        "spec": CODING_TOOLS_SPEC,
    },
    "document": {
        "system": (
            "You are a document QA assistant with ONLY lookup_passage_stub, bullets_from_text_stub, structured_report_stub. "
            "Ground answers in lookup_passage_stub when the topic matches. Education only — not tax advice. "
            "Produce a clear structured_report_stub at the end."
        ),
        "impl": DOCUMENT_TOOLS_IMPL,
        "spec": DOCUMENT_TOOLS_SPEC,
    },
}


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


def run_specialized_agent_with_client(
    client: OpenAI,
    agent_key: str,
    user_text: str,
    max_steps: int = 10,
) -> str:
    """Run one Ch12 worker; used by Ch13/14 multi-agent demos (shared client)."""
    cfg = AGENTS[agent_key]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": cfg["system"]},
        {"role": "user", "content": user_text},
    ]
    impl: dict[str, Any] = cfg["impl"]
    spec = cfg["spec"]

    for _ in range(max_steps):
        completion = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=messages,
            tools=spec,
            tool_choice="auto",
        )
        msg = completion.choices[0].message
        messages.append(assistant_to_message_dict(msg))
        if not msg.tool_calls:
            return (msg.content or "").strip()
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name not in impl:
                out = f"error: unknown tool {name!r}"
            else:
                try:
                    out = str(impl[name](**args))
                except TypeError as e:
                    out = f"error: bad arguments for {name!r}: {e}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
    return "Stopped: max_steps exceeded."


def run_specialized_agent(agent_key: str, user_text: str, max_steps: int = 10) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return run_specialized_agent_with_client(client, agent_key, user_text, max_steps=max_steps)


def cmd_list() -> None:
    print("Agents (each has a different small toolset):\n")
    for key in AGENTS:
        names = [t["function"]["name"] for t in AGENTS[key]["spec"]]
        print(f"  {key:10} tools: {', '.join(names)}")
    print("\nExample:")
    print('  python ch12_specialized_agents_demo.py research "Two stub sources on carbon pricing"')
    print('  python ch12_specialized_agents_demo.py coding "What is in common.py?"')
    print('  python ch12_specialized_agents_demo.py document "Explain deductions in a short report"')


def main() -> None:
    parser = argparse.ArgumentParser(description="Ch12: specialized agents + narrow tools (stubs)")
    parser.add_argument(
        "agent",
        nargs="?",
        choices=[*AGENTS.keys(), "list"],
        default="list",
        help="agent role or 'list'",
    )
    parser.add_argument("query", nargs="?", default=None, help="user message when agent is not list")
    args = parser.parse_args()

    if args.agent == "list":
        cmd_list()
        return

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    q = (args.query or "Introduce yourself and list the tools you are allowed to use.").strip()
    print(f"=== Agent: {args.agent} ===\n")
    print(run_specialized_agent(args.agent, q))


if __name__ == "__main__":
    main()
