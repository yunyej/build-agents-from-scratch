"""
Download sources listed in manifest.json into data/raw/.

Usage (from repo root):
  python rag_federal_individual/scripts/ingest.py
  python rag_federal_individual/scripts/ingest.py --dry-run
  python rag_federal_individual/scripts/ingest.py --only irs_p17
  python rag_federal_individual/scripts/ingest.py --only irs_p17,irs_p501
  python rag_federal_individual/scripts/ingest.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
RAW = ROOT / "data" / "raw"

USER_AGENT = "build-agents-from-scratch-rag-ingest/1.0 (educational)"

DELAY_SEC = 1.5


def load_manifest() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if "sources" not in data:
        raise SystemExit("manifest.json missing 'sources' array")
    return data


def ext_for_format(fmt: str) -> str:
    return ".pdf" if fmt == "pdf" else ".html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated source ids")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    only_set: frozenset[str] | None = None
    if args.only:
        only_set = frozenset(x.strip() for x in args.only.split(",") if x.strip())

    meta = load_manifest()
    sources = meta["sources"]
    if only_set is not None:
        sources = [s for s in sources if s["id"] in only_set]
        if not sources:
            print(f"No sources matched --only={args.only!r}", file=sys.stderr)
            sys.exit(1)

    RAW.mkdir(parents=True, exist_ok=True)

    for i, src in enumerate(sources):
        sid = src["id"]
        url = src["url"]
        fmt = src.get("format", "html")
        path = RAW / f"{sid}{ext_for_format(fmt)}"

        if path.exists() and not args.force:
            print(f"[skip exists] {sid} -> {path.name}")
            continue

        print(f"[fetch] {sid} <- {url}")
        if args.dry_run:
            continue

        if i > 0:
            time.sleep(DELAY_SEC)

        with httpx.Client(
            timeout=120.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            r = client.get(url)
            r.raise_for_status()
            path.write_bytes(r.content)
        print(f"  wrote {path.stat().st_size} bytes")

    if args.dry_run:
        print("--dry-run: no files written")


if __name__ == "__main__":
    main()
