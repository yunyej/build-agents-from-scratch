from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "rag_federal_individual" / "data" / "index"

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 512

_CITATION_RE = re.compile(r"\[\d+\]")


def load_index() -> tuple[np.ndarray, list[dict]]:
    emb_path = INDEX / "embeddings.npy"
    meta_path = INDEX / "chunks_meta.jsonl"
    if not emb_path.exists() or not meta_path.exists():
        raise SystemExit(
            "Index missing. Run:\n"
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


def search_tax_corpus(client: OpenAI, question: str, k: int = 6) -> list[dict]:
    E, rows = load_index()
    q = embed_query(client, question)
    hits = top_k(E, q, k)
    out: list[dict] = []
    for rank, (i, score) in enumerate(hits, 1):
        rec = rows[i]
        meta = rec.get("metadata", {})
        out.append(
            {
                "rank": rank,
                "score": score,
                "source_id": meta.get("source_id", ""),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "text": rec.get("text", ""),
            }
        )
    return out


def answer_with_rag(client: OpenAI, question: str, k: int = 6) -> str:
    hits = search_tax_corpus(client, question, k=k)
    sources = []
    for h in hits:
        sources.append(
            f"[{h['rank']}] {h['title']}\nURL: {h['url']}\n\n{h['text'][:8000]}"
        )
    context = "\n\n---\n\n".join(sources)

    system = (
        "You are a careful assistant for federal individual tax research. "
        "Answer ONLY using the provided sources. If the sources do not contain enough "
        "information, say so. After each factual claim, cite the source number [1], [2], etc. "
        "This is not legal or tax advice."
    )
    user = f"Question:\n{question}\n\nSources:\n{context}"

    comp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (comp.choices[0].message.content or "").strip()


def looks_grounded(answer: str) -> bool:
    if not answer:
        return False
    if "not enough" in answer.lower() or "do not contain enough" in answer.lower():
        return False
    return _CITATION_RE.search(answer) is not None


def run_agent(client: OpenAI, question: str, k: int, max_steps: int, verbose: bool) -> str:
    """
    Minimal agent loop:
      - act: retrieve+answer
      - observe: check if answer looks grounded
      - retry once with broader retrieval if needed
    """
    last = ""
    for step in range(1, max_steps + 1):
        if verbose:
            print(f"[agent] step {step}/{max_steps} (k={k})")
        last = answer_with_rag(client, question, k=k)
        if looks_grounded(last):
            return last
        # broaden search and try again
        k = min(max(k + 4, int(k * 1.7)), 20)
    return last


def main() -> None:
    argv = sys.argv[1:]
    verbose = False
    if "--verbose" in argv:
        verbose = True
        argv = [a for a in argv if a != "--verbose"]

    question = " ".join(argv).strip() or "What filing statuses does the IRS describe?"

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(OPENAI_KEY_HINT)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    # Keep this intentionally tiny: two steps is enough to demonstrate the agent pattern.
    answer = run_agent(client, question, k=6, max_steps=2, verbose=verbose)
    print(answer)


if __name__ == "__main__":
    main()

