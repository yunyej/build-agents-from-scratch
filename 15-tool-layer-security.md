# Chapter 15 — Secure the tool layer

This chapter corresponds to **Step 15** under *Phase 7 — Productionize it* in [this book’s README](./README.md). Tools are the **attack surface** of an agent: prompt injection, malicious arguments, unsafe execution, and data leakage all show up here first.

---

## 1. What to defend against

| Risk | Example | Mitigation pattern |
|------|---------|---------------------|
| **Prompt injection** | User embeds “ignore previous instructions…” | Layered: system hardening, output filtering, **no** secret data in prompts, risky-phrase heuristics (weak alone) |
| **Malicious tool arguments** | Huge strings, path traversal, shell metacharacters | **Validation**, **allowlists**, size caps, typed parameters |
| **Unsafe code execution** | Model emits `exec` or subprocess | **No arbitrary eval**; sandbox; separate low-privilege worker |
| **Data leakage** | Tool returns PII to wrong tenant | Authz on every tool call, audit logs, data scoping |

---

## 2. Runnable demo

Script: [`code/ch15_tool_security_demo.py`](./code/ch15_tool_security_demo.py)

- **`list`** — what the demo covers (no API key).
- **`dry-run`** — user-text heuristics + `safe_multiply` bounds without OpenAI.
- **`run`** — tiny agent with **only** `safe_multiply`; integers bounded; unknown tools blocked at execution boundary.

```bash
cd code
python ch15_tool_security_demo.py list
python ch15_tool_security_demo.py dry-run
python ch15_tool_security_demo.py run "What is 99 * 101?"
```

---

## 3. What’s next

**Chapter 16** — measure behavior before tuning: [Evaluation](./16-evaluation-benchmarks.md).

---

[← Chapter 14](./14-multi-agent-coordination-rules.md) · [Book home](./README.md) · [Chapter 16 →](./16-evaluation-benchmarks.md)
