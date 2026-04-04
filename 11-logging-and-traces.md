# Chapter 11 — Logging and traces

This chapter corresponds to **Step 11** under *Phase 4 — Improve reasoning and reliability* in [this book’s README](./README.md). Planning (Chapter 9), execution, and reflection (Chapter 10) produce a lot of **intermediate state**. If you only keep the final chat message, you cannot answer: *was the wrong chunk retrieved? Were tool arguments wrong? Did reflection miss a year mismatch?*

---

## 1. What to record

At minimum, persist (or stream) enough to reconstruct the run:

- User message (and optional conversation id)
- Parsed session facts (or raw extract errors)
- Plan JSON
- **Retrieval**: query / topic and the text (or chunk ids) returned
- **Tools**: name, arguments, raw output, ordering
- Reflection JSON and both draft vs final answer
- Errors / retries, **LLM round counts** and caps hit

A typical motivating bug: you need the trace to see *2023 chunk + no year filter + reflection miss*, not just “wrong number.”

---

## 2. Local vs cloud system design

The **shape** of the data is similar everywhere; what changes is **where it lives**, **who can read it**, and **retention**.

### Local (laptop, single tenant)

Typical pattern:

- **SQLite** (one file) or append-only **JSONL** logs.
- Co-located with the app; trivial to try in a demo.
- Limits: concurrent writers, no built-in cross-machine query, you manage backups and PII yourself.

Use this when you are prototyping, running evaluations offline, or want a **queryable** store without standing up a server.

### Cloud (shared service, teams, compliance)

Typical pattern:

- **OLTP database** (Postgres, etc.) for structured rows: `runs`, `tool_calls`, `retrieval_events`, …
- **Object storage** (S3/GCS) for large blobs: full prompt transcripts, raw HTTP, big retrieved documents.
- **Log / observability pipeline** (OpenTelemetry, vendor APM) for latency, errors, and sampling.
- **Multi-tenant** `tenant_id` (or `workspace_id`) on every table; **retention** and **redaction** jobs for PII.

Same logical tables often map cleanly: SQLite in the repo demo is a **schema sketch** you can port to Postgres with types tweaked (`JSONB`, timestamptz, partitioning on `created_at`).

---

## 3. Why multiple tables (instead of one JSON blob)

A single JSON document per run is fine for a first version. **Normalized tables** help when you need to:

- Filter “all runs where `baseline_tax_placeholder` was called with `married=false` but facts said married”
- Join retrieval topics to bad answers
- Index `created_at` and `tool_name` for dashboards

The runnable demo uses **separate tables** for runs, session facts, plans, tool calls, retrieval-shaped rows, and reflection—mirroring how you would split blob vs metadata in production.

**Demo SQLite tables** (see `init_schema` in the script):

| Table | Role |
|--------|------|
| `runs` | One row per invocation: timestamps, flags, status/error, LLM round count, tool count, draft/final answers |
| `session_facts` | JSON from the extractor (Phase 0) |
| `plans` | Planner JSON (Phase A), omitted when `--no-plan` |
| `tool_calls` | Ordered tool name, arguments JSON, raw output |
| `retrieval_events` | Subset of calls to `retrieve_tax_rules` (topic + snippet); in production add `source_id`, chunk ids, year filter |
| `reflections` | Full reflection JSON plus draft vs final text |

If you change the schema during experiments, delete `ch11_agent_traces.sqlite` and recreate.

---

## 4. Runnable demo

Script: [`code/ch11_logging_traces_tax_agent.py`](./code/ch11_logging_traces_tax_agent.py)

It reuses the Chapter 10 pipeline, then **writes a trace** to `ch11_agent_traces.sqlite` (configurable with `--db`).

Inspect stored runs:

```bash
python code/ch11_logging_traces_tax_agent.py --list
python code/ch11_logging_traces_tax_agent.py --show <run_id>
```

Normal run (still needs `OPENAI_API_KEY`):

```bash
python code/ch11_logging_traces_tax_agent.py 'I made $220k, married, 2 kids.'
```

(Or `cd code` and omit the `code/` prefix.)

**Not tax advice.** Stub tools only.

---

## 5. What’s next

**Phase 5** in this book’s README: narrow **specialized** agents and toolsets — [**Chapter 12**](./12-specialized-agents-narrow-tools.md) · [`code/ch12_specialized_agents_demo.py`](./code/ch12_specialized_agents_demo.py). Traces make that iteration bearable.

---

[← Chapter 10](./10-reflection-and-critique.md) · [Book home](./README.md) · [Chapter 12 →](./12-specialized-agents-narrow-tools.md)
