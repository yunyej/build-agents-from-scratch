"""
Query the local RAG index: retrieve top-k chunks, optionally answer with OpenAI using citations.

Usage:
  python rag_federal_individual/scripts/query_rag.py "What is the standard deduction?"
  python rag_federal_individual/scripts/query_rag.py "Who qualifies as head of household?" --k 8 --no-llm
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 512


def load_dotenv_any() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT.parent / "code" / ".env")
    load_dotenv(ROOT / ".env")


def load_index() -> tuple[np.ndarray, list[dict]]:
    emb_path = INDEX / "embeddings.npy"
    meta_path = INDEX / "chunks_meta.jsonl"
    if not emb_path.exists() or not meta_path.exists():
        print("Index missing. Run: python rag_federal_individual/scripts/build_rag_index.py", file=sys.stderr)
        sys.exit(1)
    E = np.load(emb_path)
    rows: list[dict] = []
    with meta_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if len(rows) != E.shape[0]:
        print("embeddings.npy row count does not match chunks_meta.jsonl", file=sys.stderr)
        sys.exit(1)
    return E, rows


def embed_query(client: OpenAI, q: str) -> np.ndarray:
    r = client.embeddings.create(
        model=EMBED_MODEL,
        input=q[:30000],
        dimensions=EMBED_DIMS,
    )
    v = np.array(r.data[0].embedding, dtype=np.float32)
    n = np.linalg.norm(v)
    if n > 0:
        v = v / n
    return v


def top_k(E: np.ndarray, q: np.ndarray, k: int) -> list[tuple[int, float]]:
    En = E / np.linalg.norm(E, axis=1, keepdims=True)
    sims = En @ q
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [(int(i), float(sims[i])) for i in idx]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default="What filing statuses does the IRS describe?")
    parser.add_argument("--k", type=int, default=5, help="number of chunks to retrieve")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="only print retrieved passages (still embeds the question via OpenAI; key required)",
    )
    args = parser.parse_args()

    load_dotenv_any()
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Set OPENAI_API_KEY in code/.env or rag_federal_individual/.env (see code/.env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    E, rows = load_index()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    q = embed_query(client, args.question)
    hits = top_k(E, q, args.k)

    print("--- Retrieved chunks (cosine similarity) ---\n")
    context_blocks: list[str] = []
    for rank, (i, score) in enumerate(hits, 1):
        rec = rows[i]
        meta = rec.get("metadata", {})
        title = meta.get("title", "")
        url = meta.get("url", "")
        sid = meta.get("source_id", "")
        print(f"[{rank}] score={score:.4f} source_id={sid}")
        print(f"    {title}")
        if url:
            print(f"    {url}")
        excerpt = rec["text"][:1200] + ("…" if len(rec["text"]) > 1200 else "")
        print(excerpt)
        print()
        context_blocks.append(
            f"--- Source {rank}: {title}\nURL: {url}\n---\n{rec['text'][:8000]}"
        )

    if args.no_llm:
        return

    context = "\n\n".join(context_blocks)
    system = (
        "You are a careful assistant for federal individual tax research. "
        "Answer ONLY using the provided sources. If the sources do not contain enough "
        "information, say so. After each factual claim, cite the source number [1], [2], etc. "
        "This is not legal or tax advice."
    )
    user = f"Question:\n{args.question}\n\nSources:\n{context}"

    comp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    ans = comp.choices[0].message.content or ""
    print("--- Model answer (grounded) ---\n")
    print(ans.strip())


if __name__ == "__main__":
    main()
