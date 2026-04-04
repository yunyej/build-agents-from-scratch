# Federal individual tax — RAG source pack

This folder supports **Step 6 (RAG)** in [Chapter 6 — Retrieval and RAG](../06-retrieval-and-rag.md).

## What you get in the repo

| Item | Role |
|------|------|
| [`manifest.json`](./manifest.json) | Curated list of URLs + ids |
| [`scripts/ingest.py`](./scripts/ingest.py) | Download each source into `data/raw/` |
| [`scripts/extract_text.py`](./scripts/extract_text.py) | PDF / HTML → `data/processed/*.txt` |
| [`scripts/chunk_to_jsonl.py`](./scripts/chunk_to_jsonl.py) | Text → `data/chunks/federal_individual.jsonl` |
| [`scripts/build_rag_index.py`](./scripts/build_rag_index.py) | OpenAI embeddings → `data/index/` |
| [`scripts/query_rag.py`](./scripts/query_rag.py) | Top-*k* retrieval + grounded answer |

`rag_federal_individual/.env` and `code/.env` are covered by the **repository root** `.gitignore`. Python caches and virtualenvs are ignored there too. **Build outputs** under `data/` (PDFs, embeddings, full chunk files) are often kept out of git in your own fork; **this repo may ship small samples** (for example partial `data/raw` HTML and a built index) so `--quick` works without a full ingest.

## Setup

From the **book repository root**:

```bash
pip install -r rag_federal_individual/requirements.txt
```

Set `OPENAI_API_KEY` in `rag_federal_individual/.env` or `code/.env`.

## End-to-end RAG (study case)

**Full rebuild** (all processed sources except skipped hub chunks — see below):

```bash
python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks
```

**Quick test** (only two IRS HTML pages; fast extract + cheap embed):

```bash
python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks --quick
```

**Query:**

```bash
python rag_federal_individual/scripts/query_rag.py "What filing statuses are described?"
python rag_federal_individual/scripts/query_rag.py "standard deduction" --no-llm
```

`--no-llm` skips the chat completion only; the **question is still embedded** with OpenAI to search the index, so `OPENAI_API_KEY` is required in both modes.

### Default corpus scope

This repo’s `manifest.json` is **IRS-focused** (pubs + 1040 instructions + a couple IRS HTML pages). It intentionally does **not** include huge statute/regulation hubs by default. Add your own statute/regulation sources only when you actually need them (cost + noise).

## Ingest only (download)

```bash
python rag_federal_individual/scripts/ingest.py
python rag_federal_individual/scripts/ingest.py --dry-run
python rag_federal_individual/scripts/ingest.py --only irs_p17
```

## Extract / chunk only

```bash
python rag_federal_individual/scripts/extract_text.py
python rag_federal_individual/scripts/extract_text.py --only irs_p17,irs_p501
python rag_federal_individual/scripts/chunk_to_jsonl.py
python rag_federal_individual/scripts/chunk_to_jsonl.py --only-sources irs_filing_status,irs_credits_deductions
```

## Scope and limits

- **Federal individual** focus; not legal advice.
- **Accuracy** depends on source year and chunking; verify against official IRS / statute for production.
- For **state** tax, add another manifest + index.

## Related

- [`06-retrieval-and-rag.md`](../06-retrieval-and-rag.md) — Chapter 6 (narrative + hands-on).
- [Book home](../README.md)
