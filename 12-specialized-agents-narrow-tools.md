# Chapter 12 — Specialized agents and narrow toolsets

This chapter corresponds to **Step 12** under *Phase 5 — Build specialized agents* in [this book’s README](./README.md). Build **several small agents** instead of one universal assistant, and give **each agent only the tools it needs**.

This matches how real products split work: different **roles**, different **tools**, different **failure modes** — easier to debug and safer than a single agent with twenty tools. At larger scale, the same pattern often becomes separate pipelines (e.g. research vs configuration vs execution) with **strict tool permissions** per role.

---

## 1. Why not one giant agent?

If every tool is available to one model, it tends to:

- call the wrong tool for the task
- mix concerns (e.g. “run code” when the user only asked for a summary)
- produce outputs that are harder to trace

**Specialization** means each agent has a **short system prompt** and a **small `tools` list** that matches its job.

---

## 2. Three starter roles (from the README)

| Agent (example) | Narrow tools (examples) |
|-------------------|---------------------------|
| **Research** | search (or RAG), clip/fetch excerpt, citation formatter |
| **Coding** | read file, run tests, calculator / safe eval |
| **Document QA** | retrieval, extract structure, formatted report |

Your real stack might swap stubs for **web APIs**, **git**, **vector DB**, or **household YAML** — the pattern stays: **one role, one tool surface**.

---

## 3. How this chapter’s demo works

Script: [`code/ch12_specialized_agents_demo.py`](./code/ch12_specialized_agents_demo.py)

- Three **named agents**: `research`, `coding`, `document`.
- Each run uses **only that agent’s** OpenAI `tools` array (the model never sees the other agents’ tools).
- All tools are **stubs** (no real web; limited file read; toy math).

List toolsets:

```bash
python code/ch12_specialized_agents_demo.py list
```

Run one agent (needs `OPENAI_API_KEY` in `code/.env`):

```bash
cd code
python ch12_specialized_agents_demo.py research "Stub search on carbon pricing and cite"
python ch12_specialized_agents_demo.py coding "Summarize common.py"
python ch12_specialized_agents_demo.py document "Write a short report on deductions"
```

---

## 4. Connection to multi-agent products

Teams often mirror this with named roles—**researcher** (retrieval), **builder** (configs or artifacts), **executor** (runs or side effects)—each allowed only its own tools. Chapter 12 is the **minimal** version: three agents in one repo with explicit OpenAI `tools` lists.

---

## 5. What’s next

**Phase 6** in this book’s README: **split roles** then **coordination rules** in one workflow:

* [Chapter 13 — Multi-agent: split roles](./13-multi-agent-split-roles.md) · [`code/ch13_multi_agent_split_roles.py`](./code/ch13_multi_agent_split_roles.py)
* [Chapter 14 — Multi-agent: coordination rules](./14-multi-agent-coordination-rules.md) · [`code/ch14_multi_agent_coordination.py`](./code/ch14_multi_agent_coordination.py)

---

[← Chapter 11](./11-logging-and-traces.md) · [Book home](./README.md) · [Chapter 13 →](./13-multi-agent-split-roles.md)
