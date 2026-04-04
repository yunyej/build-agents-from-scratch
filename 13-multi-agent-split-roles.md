# Chapter 13 — Multi-agent: split roles

This chapter corresponds to **Step 13** under *Phase 6 — Learn multi-agent design* in [this book’s README](./README.md). Use **different roles** instead of one model doing everything. A common first pattern is **supervisor → worker → critic** (or **planner → executor → critic**), or **researcher → writer → reviewer**.

It builds on [Chapter 12](./12-specialized-agents-narrow-tools.md): the **worker** is still one of the three narrow toolsets (`research`, `document`, `coding`).

---

## 1. What “split roles” means

Each step is a **different responsibility** (and usually a **separate LLM call** with a **different system prompt**):

| Role | Typical job | Tools in this demo |
|------|-------------|---------------------|
| **Supervisor / planner** | Decide *which* specialist should act | None — outputs JSON (`worker` + short plan) |
| **Worker / executor** | Do the task with specialist tools | Only that worker’s Ch12 tools |
| **Critic / reviewer** | Comment on quality / gaps | None — free-text critique |

The point is **specialization**: the supervisor does not see file-read tools; the worker does not choose the route; the critic does not call search.

---

## 2. Runnable demo

Script: [`code/ch13_multi_agent_split_roles.py`](./code/ch13_multi_agent_split_roles.py)

```bash
cd code
python ch13_multi_agent_split_roles.py list
python ch13_multi_agent_split_roles.py run "Find stub sources on climate"
```

Requires `OPENAI_API_KEY` in `code/.env` for `run`.

Output sections: **Supervisor** (pick + plan), **Worker output**, **Critic**.

---

## 3. Product-scale analogy

In bigger systems, a **planner** (or router) often chooses which specialist runs next; **research**, **build**, and **execute** steps are separate concerns with different tools and credentials. Chapter 13 is the **minimal** version of that shape in one script.

---

## 4. What’s next

**Chapter 14** — coordination rules: **who** may use tools, **shared state**, **reviewer approval**, **retry**, **escalation**: [Chapter 14](./14-multi-agent-coordination-rules.md).

---

[← Chapter 12](./12-specialized-agents-narrow-tools.md) · [Book home](./README.md) · [Chapter 14 →](./14-multi-agent-coordination-rules.md)
