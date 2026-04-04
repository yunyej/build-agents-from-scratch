"""
Chunk data/processed/*.txt into data/chunks/federal_individual.jsonl

Each line: {"id": "...", "text": "...", "metadata": {...}}

Usage:
  python rag_federal_individual/scripts/chunk_to_jsonl.py
  python rag_federal_individual/scripts/chunk_to_jsonl.py --only-sources irs_filing_status,irs_credits_deductions
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
PROCESSED = ROOT / "data" / "processed"
CHUNKS = ROOT / "data" / "chunks"


def char_chunks(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fixed-size windows with trailing overlap so boundaries do not hard-cut mid-thought."""
    body = re.sub(r"\r\n", "\n", text)
    if "---\n\n" in body:
        body = body.split("---\n\n", 1)[-1]
    body = body.strip()
    if not body:
        return []

    chunks: list[str] = []
    start = 0
    n = len(body)
    while start < n:
        end = min(start + max_chars, n)
        chunks.append(body[start:end])
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-chars", type=int, default=1400)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument(
        "--only-sources",
        help="comma-separated source ids matching processed/*.txt stems",
    )
    args = parser.parse_args()

    only_set: frozenset[str] | None = None
    if args.only_sources:
        only_set = frozenset(x.strip() for x in args.only_sources.split(",") if x.strip())

    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in meta["sources"]}
    corpus_id = meta.get("corpus_id", "")

    CHUNKS.mkdir(parents=True, exist_ok=True)
    out_path = CHUNKS / "federal_individual.jsonl"

    lines_out: list[str] = []
    for txt_path in sorted(PROCESSED.glob("*.txt")):
        sid = txt_path.stem
        if only_set is not None and sid not in only_set:
            continue
        src = by_id.get(sid, {})
        raw_text = txt_path.read_text(encoding="utf-8")
        pieces = char_chunks(raw_text, args.max_chars, args.overlap)

        for j, piece in enumerate(pieces):
            h = hashlib.sha256(piece.encode("utf-8")).hexdigest()[:12]
            cid = f"{sid}_chunk_{j}_{h}"
            rec = {
                "id": cid,
                "text": piece,
                "metadata": {
                    "source_id": sid,
                    "title": src.get("title", ""),
                    "url": src.get("url", ""),
                    "category": src.get("category", ""),
                    "corpus_id": corpus_id,
                },
            }
            lines_out.append(json.dumps(rec, ensure_ascii=False))

    out_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines_out)} chunks -> {out_path}")


if __name__ == "__main__":
    main()
