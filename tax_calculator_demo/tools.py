"""Tool implementations and OpenAI `tools` schema.

`retrieve_tax_rules` uses `rag_federal_individual` when `data/index` exists; otherwise short stubs.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from tax_calculator_demo.config import Settings

_LOG = logging.getLogger(__name__)

_rag_client: OpenAI | None = None
_rag_settings: Settings | None = None


def configure_rag(client: OpenAI, settings: Settings) -> None:
    """Called by the service before each run so retrieval can embed queries."""
    global _rag_client, _rag_settings
    _rag_client = client
    _rag_settings = settings


def _stub_retrieve(topic: str) -> str:
    t = topic.lower()
    if "401" in t or "retirement" in t:
        return (
            "[stub retrieve — build RAG index] Pre-tax 401(k) contributions generally reduce taxable wages for federal income tax. "
            "Limits and rules depend on year and plan; verify with IRS and your plan administrator."
        )
    if "roth" in t or "traditional" in t:
        return (
            "[stub retrieve — build RAG index] Traditional vs Roth: traditional often defers tax on contribution; "
            "Roth uses after-tax dollars with qualified distributions potentially tax-free. "
            "Tradeoffs depend on brackets and horizon—verify with a professional."
        )
    if "standard" in t or "deduction" in t or "itemiz" in t:
        return (
            "[stub retrieve — build RAG index] Most filers take the standard deduction; itemizing helps when "
            "deductible expenses exceed the standard amount for that tax year. Use official IRS figures for the year."
        )
    return (
        "[stub retrieve — build RAG index] No local index found under RAG_ROOT. "
        "Run: python rag_federal_individual/scripts/build_rag_index.py (from repo root). "
        "General: confirm filing status, dependents, and tax year before estimating."
    )


def retrieve_tax_rules(topic: str) -> str:
    """Federal passages via vector RAG when index exists; else stub text."""
    if _rag_client is not None and _rag_settings is not None:
        from tax_calculator_demo import rag_retrieval

        root = _rag_settings.resolved_rag_root()
        if rag_retrieval.index_available(root):
            try:
                return rag_retrieval.retrieve_passages(_rag_client, _rag_settings, topic)
            except Exception as e:
                _LOG.exception("rag_retrieve_failed topic=%r", topic)
                return f"[retrieve error] {type(e).__name__}: {e}\n\n{_stub_retrieve(topic)}"
    return _stub_retrieve(topic)


def baseline_tax_placeholder(annual_income: float, married: bool, num_children: int) -> str:
    """Toy placeholder — NOT real tax law. Swap for a licensed engine or external API."""
    if annual_income <= 0:
        return "error: annual_income must be positive"
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
            "description": (
                "Retrieve federal individual tax passages: uses the local RAG index under RAG_ROOT when built; "
                "otherwise short stubs. Pass a concise topic or query string."
            ),
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
            "description": "Placeholder baseline estimate for demonstration only—not real tax law.",
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
