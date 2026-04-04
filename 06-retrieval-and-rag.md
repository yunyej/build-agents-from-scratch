# Chapter 6 — Retrieval and RAG

This chapter corresponds to **Step 6** under *Phase 3 — Make it useful* in [this book’s README](./README.md). It assumes [Chapter 1](./01-llms-at-a-practical-level.md) (tokens, hallucination limits) and [Chapter 3](./03-chatbot-vs-agent-and-the-loop.md) (agent loop).

**Deliverable.** You can run the **federal individual** sample pipeline under [`rag_federal_individual/`](./rag_federal_individual/README.md), query with retrieval (and optional grounded generation), and explain **why RAG** reduces confabulation risk compared with raw completion.

**Not legal or tax advice.** The IRS-oriented corpus is a learning pattern only.

---

## 1. Why retrieval helps

Large language models **do not reliably know** proprietary, recent, or narrow-domain facts. They may **confabulate** plausible but false details ([Chapter 1](./01-llms-at-a-practical-level.md)).

**Retrieval-Augmented Generation (RAG)** means: before (or while) the model answers, you **fetch** relevant passages from a **document store** you control, inject them into the context, and ask the model to **use that evidence**. Answers are easier to **audit** if you require **citations** to retrieved chunks.

Classic reference: [Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (NeurIPS 2020)](https://arxiv.org/abs/2005.11401).

---

## 2. End-to-end pipeline (mental model)

1. **Ingest** — acquire documents; record metadata (source id, URL, date, version).  
2. **Parse / extract** — turn bytes into clean text.  
3. **Chunk** — split text to fit embedding and context limits; optional overlap between chunks.  
4. **Embed** — map each chunk to a **vector** with an embedding model.  
5. **Index** — store vectors for fast **approximate nearest-neighbor** search.  
6. **Retrieve** — embed the query, find top-*k* similar chunks.  
7. **Augment** — put retrieved text in the prompt (or tool result) with clear delimiters.  
8. **Generate** — model answers **conditioned on** those passages; policy may require “not found.”

Same idea appears as “vector store,” “knowledge base,” or vendor file search: **retrieve, then generate**.

---

## 3. Chunking, embeddings, search, quality, grounding

**Chunking.** Chunks should be **semantically coherent** and sized so several fit in context after retrieval; **overlap** between adjacent chunks reduces broken definitions. Attach **metadata** (source, section, date, jurisdiction) for citations and filters.

**Embeddings.** An embedding model maps text to a fixed-length vector; similar meaning → closer vectors (often **cosine similarity**). Use the **same** embedding model for **index and query**. See [OpenAI embeddings](https://platform.openai.com/docs/guides/embeddings).

**Vector search.** Production systems use **approximate** nearest neighbors (FAISS, HNSW, pgvector, managed vector DBs, etc.). Use top-*k* and/or a **similarity threshold**; **hybrid** keyword (BM25) + dense search often helps for form numbers and rare tokens.

**Quality.** “Good RAG” means the **right chunks** rank high—not only fluent text. Offline: recall@*k*, MRR, nDCG; tools like [RAGAS](https://docs.ragas.io/) are helpers, not ground truth for law. Human check: does the cited passage **support** the claim?

**Grounding policy.** Instruct the model: answer **only** from retrieved text; **cite**; say **not found** when nothing applies. Retrieval can be a **tool** (`search_docs(query)`) or **middleware** before each completion.

---

## 4. What you are building (this repo)

Sample corpus: **federal individual** IRS-oriented sources in [`rag_federal_individual/`](./rag_federal_individual/README.md).

```text
data/raw/*.pdf|.html
    → extract_text.py → data/processed/*.txt
    → chunk_to_jsonl.py → data/chunks/federal_individual.jsonl
    → build_rag_index.py → data/index/embeddings.npy + chunks_meta.jsonl
    → query_rag.py → retrieval + optional grounded answer
```

The **agent loop** from earlier chapters can treat this as a **tool** (`search_tax_corpus`) later; the scripts expose a CLI first.

---

## 5. Prerequisites

- Python 3.10+  
- `OPENAI_API_KEY` in `rag_federal_individual/.env` or `code/.env`  
- Raw files under `rag_federal_individual/data/raw/` (after ingest)

From the **repository root**:

```bash
pip install -r rag_federal_individual/requirements.txt
```

---

## 6. Build the index

The manifest is **IRS-focused**; a full US Code Title 26 HTML hub is intentionally **not** included by default (huge and noisy).

```bash
python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks
```

**Fast sanity check** (two small HTML sources only):

```bash
python rag_federal_individual/scripts/build_rag_index.py --rebuild-chunks --quick
```

If `data/processed/` is already good and you only changed chunking params:

```bash
python rag_federal_individual/scripts/build_rag_index.py --skip-extract --rebuild-chunks
```

Typical build outputs: `rag_federal_individual/data/index/embeddings.npy`, `chunks_meta.jsonl`, `index_manifest.json`. You can keep these local-only in your fork; this repo may include a **small sample index** so quick queries work without a full rebuild.

---

## 7. Query

Retrieve top 5 chunks and ask the model to answer **only** from them:

```bash
python rag_federal_individual/scripts/query_rag.py "What filing statuses are mentioned?"
python rag_federal_individual/scripts/query_rag.py "What does the IRS say about education credits?" --k 8
```

**Retrieval only** (no chat completion):

```bash
python rag_federal_individual/scripts/query_rag.py "standard deduction" --no-llm
```

---

## 8. How the scripts map to the pipeline

| Idea | Where it appears |
|------|------------------|
| Chunking | `chunk_to_jsonl.py` (size + overlap) |
| Embeddings | `text-embedding-3-small`, 512 dims, batched |
| Vector search | Cosine similarity on normalized vectors (`build_rag_index` / `query_rag`) |
| Grounding | System prompt: answer only from sources + cite `[1]`, `[2]` |
| Quality | Tune `--k`, chunk size, and manifest scope |

---

## 9. Next steps (when you are ready)

- Add **hybrid** search (BM25 + dense) for form numbers and IRC citations.  
- Store **tax year** and **document version** in chunk metadata; filter at query time.  
- **Eval**: hold-out questions; check citation correctness.  
- Wrap `query_rag` as an **OpenAI tool** inside your Chapter 4-style agent loop.  

---

## 10. Minimal agent with RAG

You have a **retriever** (`query_rag.py`) and a **local index** (`rag_federal_individual/data/index/*`). An agent with RAG calls something like `search_tax_corpus(question)`, reads the result, and may retrieve again (broader query or higher *k*) before a final answer.

From the **repository root**:

```bash
python code/ch06_simple_rag_agent.py "What is the standard deduction?"
python code/ch06_simple_rag_agent.py --verbose "Who qualifies as head of household?"
```

Or: `cd code` then `python ch06_simple_rag_agent.py ...`.

- **Tool use**: `search_tax_corpus()` (vector retrieval over the local index).  
- **Loop**: up to 2 steps (retrieve → answer; optionally broaden → answer again).  
- **Stop**: early exit when the answer looks grounded (e.g. citations like `[1]`).  

---

## 11. Suggested reading

1. [Lewis et al. — RAG (paper)](https://arxiv.org/abs/2005.11401) — skim sections 2–3.  
2. [OpenAI — Embeddings](https://platform.openai.com/docs/guides/embeddings) and current retrieval / file product docs.  
3. [Anthropic — Long-context and documents](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips).  
4. [Google Gemini — grounding overview](https://ai.google.dev/gemini-api/docs/google-search) (APIs evolve).  
5. Optional: [Gao et al., RAG survey](https://arxiv.org/abs/2312.10997).  

---

[← Chapter 5](./05-stop-conditions-and-safeguards.md) · [Book home](./README.md) · [Chapter 7 →](./07-short-term-memory-session.md) · [Corpus README](./rag_federal_individual/README.md)
