# Tax calculator demo (single-agent product shell)

A **production-style** layout for the educational pipeline from [*What an agent actually is*](../README.md) (Chapters 9–11): structured session facts, planning JSON, tool loop with trace, reflection, and **SQLite** run history.

**Retrieval** uses the **`rag_federal_individual`** corpus when `rag_federal_individual/data/index/` exists (same index as [`query_rag.py`](../rag_federal_individual/scripts/query_rag.py)). If the index is missing, `retrieve_tax_rules` falls back to short stubs.

This is **not** tax, legal, or investment advice. The baseline tool is **toy** math unless you replace it.

---

## Repository layout

- **`tax_calculator_demo/`** (this folder) — Python package and CLI.
- **`rag_federal_individual/`** — ingest, chunk, embed, and **RAG data** (`data/index/embeddings.npy`, `chunks_meta.jsonl`).
- **Agent trace DB** — default `tax_calculator_demo/data/traces.sqlite` (operational logs; gitignored at repo root).

---

## How to run the CLI

Run from the **repository root** (`build-agents-from-scratch`) so Python can import the package:

```bash
cd build-agents-from-scratch
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r tax_calculator_demo/requirements.txt
```

**API key:** either set `OPENAI_API_KEY` in the shared **[`code/.env`](../code/.env)** (loaded first), **or** copy `tax_calculator_demo/.env.example` to `tax_calculator_demo/.env` and set the key there.

Optionally set `RAG_ROOT` if the corpus is not at the default sibling path `rag_federal_individual/`.

```bash
cd build-agents-from-scratch
python -m tax_calculator_demo run "I made $220k, married, 2 kids — baseline and ideas for next year."
python -m tax_calculator_demo list-runs
python -m tax_calculator_demo show <run_id>
```

PowerShell: use **single-quoted** strings if the message contains `$`.

`list-runs` / `show` do not call OpenAI; an empty `OPENAI_API_KEY` is allowed for those commands.

---

## Build the RAG index (federal corpus)

From repo root:

```bash
pip install -r rag_federal_individual/requirements.txt
python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks --quick
```

Then `retrieve_tax_rules` will return real chunks. See [`rag_federal_individual/README.md`](../rag_federal_individual/README.md).

---

## Package modules

| Module | Role |
|--------|------|
| `config.py` | `pydantic-settings`, `RAG_ROOT`, trace path, model, retries-related timeouts |
| `rag_retrieval.py` | Load index, embed query, top-k (aligned with study-case RAG) |
| `tools.py` | `retrieve_tax_rules` (RAG or stub), `baseline_tax_placeholder` |
| `llm_pipeline.py` | Facts, plan, execution + trace, reflection |
| `trace_store.py` | SQLite schema for runs / tools / retrieval rows / reflection |
| `service.py` | `TaxPlanningAgentService` |
| `cli.py` | `run`, `list-runs`, `show` |

---

## Flags (`run`)

- `--no-plan` / `--no-reflect` — toggle phases
- `--no-persist` — skip SQLite
- `--json` — full structured result
- `--quiet` — answer text only

---

## Production extensions

Swap `baseline_tax_placeholder`, add chunk `source_id` / year filters in `rag_retrieval`, move traces to Postgres, add auth and PII policies. Same ideas as [Chapter 11](../11-logging-and-traces.md).

---

Educational sample code only. Licensed with the rest of this repository ([CC BY-NC 4.0](../LICENSE)).
