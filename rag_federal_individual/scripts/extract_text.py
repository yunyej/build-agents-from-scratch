"""
Extract plain text from data/raw into data/processed/{id}.txt

Usage:
  python rag_federal_individual/scripts/extract_text.py
  python rag_federal_individual/scripts/extract_text.py --only irs_filing_status
  python rag_federal_individual/scripts/extract_text.py --only irs_filing_status,irs_credits_deductions
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


_WORD_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SPACE_AROUND_NEWLINES = re.compile(r"[ \t]+\n")
_MANY_NEWLINES = re.compile(r"\n{3,}")


def normalize_text(t: str) -> str:
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _WORD_HYPHEN_BREAK.sub(r"\1\2", t)
    t = _SPACE_AROUND_NEWLINES.sub("\n", t)
    t = _MANY_NEWLINES.sub("\n\n", t)
    return t.strip()


def pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return "[extract error: PDF is encrypted]\n"
    parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        t = page.extract_text() or ""
        t = normalize_text(t)
        if not t:
            continue
        parts.append(f"[PAGE {i}]\n{t}")
    return "\n\n".join(parts).strip() + ("\n" if parts else "")


def html_to_text(path: Path) -> str:
    raw = path.read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return normalize_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        help="comma-separated source ids (e.g. irs_p17 or irs_filing_status,irs_credits_deductions)",
    )
    args = parser.parse_args()

    only_set: frozenset[str] | None = None
    if args.only:
        only_set = frozenset(x.strip() for x in args.only.split(",") if x.strip())

    meta = load_manifest()
    PROCESSED.mkdir(parents=True, exist_ok=True)

    for src in meta["sources"]:
        sid = src["id"]
        if only_set is not None and sid not in only_set:
            continue
        fmt = src.get("format", "html")
        ext = ".pdf" if fmt == "pdf" else ".html"
        src_path = RAW / f"{sid}{ext}"
        if not src_path.exists():
            print(f"[missing raw] {src_path} — run ingest.py first", file=sys.stderr)
            continue

        out_path = PROCESSED / f"{sid}.txt"
        print(f"[extract] {sid}")

        if fmt == "pdf":
            text = pdf_to_text(src_path)
        else:
            text = html_to_text(src_path)

        header = f"SOURCE_ID: {sid}\nTITLE: {src.get('title', '')}\nURL: {src.get('url', '')}\n---\n\n"
        out_path.write_text(header + text, encoding="utf-8")
        print(f"  -> {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main()
