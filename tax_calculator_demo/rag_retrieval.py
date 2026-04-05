"""Vector retrieval over `rag_federal_individual/data/index` (same layout as `query_rag.py`)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
from openai import OpenAI

from tax_calculator_demo.config import Settings

_LOG = logging.getLogger(__name__)

_INDEX_CACHE: tuple[np.ndarray, list[dict]] | None = None


def clear_index_cache() -> None:
    global _INDEX_CACHE
    _INDEX_CACHE = None


def index_paths(rag_root: Path) -> tuple[Path, Path]:
    base = rag_root / "data" / "index"
    return base / "embeddings.npy", base / "chunks_meta.jsonl"


def index_available(rag_root: Path) -> bool:
    e, m = index_paths(rag_root)
    return e.is_file() and m.is_file()


def load_index(rag_root: Path) -> tuple[np.ndarray, list[dict]]:
    """Load embeddings + chunk metadata; cached per process."""
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    emb_path, meta_path = index_paths(rag_root)
    E = np.load(emb_path)
    rows: list[dict] = []
    with meta_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if len(rows) != E.shape[0]:
        raise ValueError("embeddings.npy row count does not match chunks_meta.jsonl")
    _INDEX_CACHE = (E, rows)
    _LOG.info("rag_index_loaded chunks=%s path=%s", len(rows), rag_root)
    return _INDEX_CACHE


def embed_query(client: OpenAI, model: str, dimensions: int, q: str) -> np.ndarray:
    r = client.embeddings.create(
        model=model,
        input=q[:30000],
        dimensions=dimensions,
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


def retrieve_passages(client: OpenAI, settings: Settings, topic: str) -> str:
    """Return formatted context blocks for the tool (no second LLM call here)."""
    rag_root = settings.resolved_rag_root()
    E, rows = load_index(rag_root)
    qvec = embed_query(
        client,
        settings.rag_embed_model,
        settings.rag_embed_dimensions,
        topic,
    )
    hits = top_k(E, qvec, settings.rag_top_k)
    parts = [
        f"[federal RAG] top-{len(hits)} chunks (cosine) from {rag_root.as_posix()} — not legal/tax advice; verify sources."
    ]
    for rank, (i, score) in enumerate(hits, 1):
        rec = rows[i]
        meta = rec.get("metadata", {})
        sid = meta.get("source_id", "")
        title = meta.get("title", "")
        url = meta.get("url", "")
        text = (rec.get("text") or "")[:4000]
        parts.append(
            f"--- [{rank}] score={score:.4f} source_id={sid}\n"
            f"title: {title}\nurl: {url}\n---\n{text}"
        )
    return "\n\n".join(parts)
