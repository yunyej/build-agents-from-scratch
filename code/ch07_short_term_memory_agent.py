from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

# Book repository root (parent of code/)
ROOT = Path(__file__).resolve().parents[1]
RAG_INDEX = ROOT / "rag_federal_individual" / "data" / "index"

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 512
CHAT_MODEL = "gpt-4o-mini"


def load_index() -> tuple[np.ndarray, list[dict]]:
    emb_path = RAG_INDEX / "embeddings.npy"
    meta_path = RAG_INDEX / "chunks_meta.jsonl"
    if not emb_path.exists() or not meta_path.exists():
        raise SystemExit(
            "RAG index missing. Run:\n"
            "  python rag_federal_individual/scripts/build_rag_index.py\n"
        )
    E = np.load(emb_path)
    rows: list[dict] = []
    with meta_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if len(rows) != E.shape[0]:
        raise SystemExit("Index mismatch: embeddings.npy rows != chunks_meta.jsonl rows")
    return E, rows


def embed_query(client: OpenAI, q: str) -> np.ndarray:
    r = client.embeddings.create(model=EMBED_MODEL, input=q[:30000], dimensions=EMBED_DIMS)
    v = np.array(r.data[0].embedding, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def top_k(E: np.ndarray, q: np.ndarray, k: int) -> list[tuple[int, float]]:
    En = E / np.linalg.norm(E, axis=1, keepdims=True)
    sims = En @ q
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [(int(i), float(sims[i])) for i in idx]


def search_tax_corpus(client: OpenAI, question: str, k: int = 6) -> str:
    """
    Tool: return top-k retrieved passages as a compact text bundle.
    Kept as plain text so it is easy to display and store in session memory.
    """
    E, rows = load_index()
    q = embed_query(client, question)
    hits = top_k(E, q, k)
    blocks: list[str] = []
    for rank, (i, score) in enumerate(hits, 1):
        rec = rows[i]
        meta = rec.get("metadata", {})
        title = meta.get("title", "")
        url = meta.get("url", "")
        sid = meta.get("source_id", "")
        text = (rec.get("text") or "")[:1600]
        blocks.append(
            f"[{rank}] score={score:.4f} source_id={sid}\n{title}\n{url}\n\n{text}"
        )
    return "\n\n---\n\n".join(blocks)


TOOLS_IMPL: dict[str, Any] = {"search_tax_corpus": search_tax_corpus}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search_tax_corpus",
            "description": (
                "Search the local federal individual tax corpus and return the top passages. "
                "Use when you need exact details from the IRS documents. "
                "Prefer using it before making factual claims about tax rules."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 12, "default": 6},
                },
                "required": ["question"],
            },
        },
    }
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


_INCOME_RE = re.compile(r"\b(?:income|salary)\s*(?:is|=)?\s*\$?\s*(\d{2,6})\b", re.I)
_KIDS_RE = re.compile(r"\b(\d+)\s*(?:kids|children|dependents)\b", re.I)
_MARRIED_RE = re.compile(r"\bmarried\b", re.I)


@dataclass
class SessionMemory:
    facts: dict[str, Any] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)
    summary: str = ""
    last_tool_results: list[str] = field(default_factory=list)

    def observe_user_text(self, text: str) -> None:
        # Extremely small heuristic extractor. In real systems you typically do this with a model + schema.
        m = _INCOME_RE.search(text)
        if m:
            self.facts["income_usd"] = int(m.group(1))
        m = _KIDS_RE.search(text)
        if m:
            self.facts["num_children"] = int(m.group(1))
        if _MARRIED_RE.search(text):
            # Keep it coarse; don’t infer MFJ/MFS without user saying.
            self.facts["marital_status"] = "married"

    def add_tool_result(self, tool_name: str, content: str) -> None:
        blob = f"{tool_name}:\n{content}"
        self.last_tool_results.append(blob)
        self.last_tool_results = self.last_tool_results[-3:]

    def memory_message(self) -> str:
        facts = json.dumps(self.facts, ensure_ascii=False, indent=2)
        open_q = "\n".join(f"- {q}" for q in self.open_questions) or "- (none)"
        tools = "\n\n".join(self.last_tool_results) or "(none)"
        summary = self.summary.strip() or "(none yet)"
        return (
            "[MEMORY]\n"
            f"facts:\n{facts}\n\n"
            f"open_questions:\n{open_q}\n\n"
            f"summary:\n{summary}\n\n"
            f"recent_tool_results:\n{tools}\n"
        )


def update_summary(client: OpenAI, memory: SessionMemory, last_user: str, last_assistant: str) -> str:
    system = (
        "You update a short session summary for an assistant. "
        "Write 2-5 bullet points. Keep only stable facts and the current goal. "
        "Do NOT include secrets or long quotes."
    )
    user = (
        f"Current summary:\n{memory.summary}\n\n"
        f"Last user message:\n{last_user}\n\n"
        f"Last assistant message:\n{last_assistant}\n\n"
        "Return updated summary bullets."
    )
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (r.choices[0].message.content or "").strip()


def run_one_turn(
    client: OpenAI,
    memory: SessionMemory,
    transcript: list[dict[str, Any]],
    user_text: str,
    max_tool_steps: int = 6,
) -> str:
    memory.observe_user_text(user_text)

    # Build a “working” messages list for this turn:
    # system + memory injection + transcript so far + current user message.
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a careful assistant for federal individual tax research. "
                "Use the provided [MEMORY] to stay consistent across turns. "
                "When you need exact tax details, call search_tax_corpus. "
                "After tools return, answer with citations like [1], [2] when using tool content. "
                "If you don't have enough info, ask a short clarifying question."
            ),
        },
        {"role": "user", "content": memory.memory_message()},
    ]
    messages.extend(transcript)
    messages.append({"role": "user", "content": user_text})

    for _ in range(max_tool_steps):
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
                    out = str(TOOLS_IMPL[name](client=client, **args))
                except TypeError as e:
                    out = f"error: bad arguments for {name!r}: {e}"
            memory.add_tool_result(name, out[:4000])
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})

    return "Stopped: max_tool_steps exceeded."


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(OPENAI_KEY_HINT)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    memory = SessionMemory()
    transcript: list[dict[str, Any]] = []

    print("Short-term memory agent (type messages; empty line exits).")
    while True:
        try:
            user_text = input("\nYou> ").strip()
        except EOFError:
            break
        if not user_text:
            break

        assistant_text = run_one_turn(client, memory, transcript, user_text)
        print(f"\nAgent> {assistant_text}")

        # Persist this turn into transcript (the “short-term memory” baseline)
        transcript.append({"role": "user", "content": user_text})
        transcript.append({"role": "assistant", "content": assistant_text})
        transcript = transcript[-12:]  # keep the last few turns

        memory.summary = update_summary(client, memory, user_text, assistant_text)


if __name__ == "__main__":
    main()

