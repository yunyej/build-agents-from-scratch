# Chapter 14 — Multi-agent: coordination rules

This chapter corresponds to **Step 14** under *Phase 6 — Learn multi-agent design* in [this book’s README](./README.md). Decide **who may call tools**, who **approves** output, how agents **share memory**, and when to **escalate**. Without this, multi-agent flows become hard to debug and unsafe.

---

## 1. What this chapter encodes in code

The demo [`code/ch14_multi_agent_coordination.py`](./code/ch14_multi_agent_coordination.py) implements a small **policy**:

| Rule | Behavior |
|------|----------|
| **Tool permissions** | Only the **chosen worker** (`research` / `document` / `coding`) runs a tool loop. **Supervisor** and **reviewer** use `chat.completions` **without** `tools=`. |
| **Shared memory** | A `SharedRunState` dataclass accumulates: user request, supervisor pick/plan, each worker attempt, each reviewer JSON, `final_answer`, `escalation`, `tool_user_only`. |
| **Approval** | **Reviewer** returns JSON: `approved`, `notes`, `escalate`. |
| **Retry** | If not approved and **not** escalated, **one** extra worker turn with reviewer `notes` appended to the user prompt. |
| **Escalation** | If `escalate: true`, the run **stops** after that review; `escalation` is set so a UI could route to a human. |

This is still a **tutorial** gate — production systems add authz, audit logs, and stricter schemas.

---

## 2. Runnable demo

```bash
cd code
python ch14_multi_agent_coordination.py list
python ch14_multi_agent_coordination.py run "Explain the 401k stub passage briefly"
```

`run` prints **`shared_run_state` as JSON** (good for inspection and tests).

Uses the same **supervisor routing** as [Chapter 13](./13-multi-agent-split-roles.md) (`supervisor_route` from `ch13_multi_agent_split_roles.py`).

---

## 3. Relation to your product plan

The optional *PRODUCT_STRUCTURE_AWS* note in the parent monorepo (see [Further reading outside this book](./README.md#further-reading-outside-this-book)) describes **coordination** at scale (queues, tenancy, traces). Chapter 14 is the **same ideas** in one process and one JSON blob.

---

## 4. What’s next

**Phase 7** — [Chapter 15](./15-tool-layer-security.md) (tool security) · [Chapter 16](./16-evaluation-benchmarks.md) (evaluation) · [Chapter 17](./17-latency-cost-optimization.md) (latency/cost) · [Chapter 18](./18-deploy-observability.md) (observability)

---

[← Chapter 13](./13-multi-agent-split-roles.md) · [Book home](./README.md) · [Chapter 15 →](./15-tool-layer-security.md)
