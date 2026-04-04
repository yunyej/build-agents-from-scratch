"""
Build a local vector index from chunked corpus (OpenAI embeddings).

Steps:
  1) extract_text.py  -> data/processed/*.txt
  2) chunk_to_jsonl.py -> data/chunks/federal_individual.jsonl
  3) Embed each chunk (batched) -> data/index/

Default: embed all chunks found in the chunk file.

Usage (repo root):
  pip install -r rag_federal_individual/requirements.txt
  set OPENAI_API_KEY in .env
  python rag_federal_individual/scripts/build_rag_index.py
  python rag_federal_individual/scripts/build_rag_index.py --quick
  python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CHUNKS = ROOT / "data" / "chunks"
INDEX = ROOT / "data" / "index"
CHUNK_FILE = CHUNKS / "federal_individual.jsonl"

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 512
BATCH_SIZE = 64
MAX_CHARS_PER_CHUNK = 30000

QUICK_ONLY = frozenset({"irs_filing_status", "irs_credits_deductions"})


def load_dotenv_any() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # Prefer code/.env; rag/.env fills missing keys (same as code/common.py).
    load_dotenv(ROOT.parent / "code" / ".env")
    load_dotenv(ROOT / ".env")


def run_pipeline_steps(skip_extract: bool, quick: bool) -> None:
    py = sys.executable
    only_csv = ",".join(sorted(QUICK_ONLY)) if quick else None

    if not skip_extract:
        print("[build] running extract_text.py …")
        ext_cmd = [py, str(SCRIPTS / "extract_text.py")]
        if only_csv:
            ext_cmd.extend(["--only", only_csv])
        subprocess.run(ext_cmd, check=True)
    else:
        print("[build] skipping extract_text.py")

    print("[build] running chunk_to_jsonl.py …")
    chunk_cmd = [py, str(SCRIPTS / "chunk_to_jsonl.py")]
    if only_csv:
        chunk_cmd.extend(["--only-sources", only_csv])
    subprocess.run(chunk_cmd, check=True)


def read_chunks(
    path: Path,
    only_ids: frozenset[str] | None,
) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sid = rec.get("metadata", {}).get("source_id", "")
            if only_ids is not None and sid not in only_ids:
                continue
            text = rec.get("text", "").strip()
            if len(text) < 20:
                continue
            rows.append(rec)
    return rows


def embed_batches(client: OpenAI, texts: list[str]) -> np.ndarray:
    vectors: list[list[float]] = []
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="embedding batches"):
        batch = [t[:MAX_CHARS_PER_CHUNK] for t in texts[i : i + BATCH_SIZE]]
        r = client.embeddings.create(model=EMBED_MODEL, input=batch, dimensions=EMBED_DIMS)
        items = list(r.data)
        if items and hasattr(items[0], "index"):
            items.sort(key=lambda d: d.index)
        for item in items:
            vectors.append(item.embedding)
    return np.array(vectors, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-extract", action="store_true", help="reuse data/processed/*.txt")
    parser.add_argument(
        "--rebuild-chunks",
        action="store_true",
        help="re-run extract (unless --skip-extract) and chunk_to_jsonl before embedding",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="only embed irs_filing_status + irs_credits_deductions",
    )
    args = parser.parse_args()

    load_dotenv_any()
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Set OPENAI_API_KEY in code/.env or rag_federal_individual/.env (see code/.env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.rebuild_chunks or not CHUNK_FILE.exists():
        run_pipeline_steps(skip_extract=args.skip_extract, quick=args.quick)

    if not CHUNK_FILE.exists():
        print(f"Missing {CHUNK_FILE}", file=sys.stderr)
        sys.exit(1)

    only = QUICK_ONLY if args.quick else None
    records = read_chunks(CHUNK_FILE, only)
    if not records:
        print("No chunks after filters. Check processed/*.txt and filters.", file=sys.stderr)
        sys.exit(1)

    texts = [r["text"] for r in records]
    print(f"[build] embedding {len(texts)} chunks ({EMBED_MODEL}, dim={EMBED_DIMS}) …")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    matrix = embed_batches(client, texts)

    INDEX.mkdir(parents=True, exist_ok=True)
    np.save(INDEX / "embeddings.npy", matrix)

    meta_path = INDEX / "chunks_meta.jsonl"
    with meta_path.open("w", encoding="utf-8") as out:
        for rec in records:
            out.write(
                json.dumps(
                    {
                        "id": rec["id"],
                        "text": rec["text"],
                        "metadata": rec.get("metadata", {}),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    manifest = {
        "embed_model": EMBED_MODEL,
        "dimensions": EMBED_DIMS,
        "num_chunks": len(records),
        "quick_mode": args.quick,
    }
    (INDEX / "index_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[build] wrote {INDEX / 'embeddings.npy'} and {meta_path}")


if __name__ == "__main__":
    main()
