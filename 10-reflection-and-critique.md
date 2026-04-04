# Chapter 10 — Reflection and critique

This chapter corresponds to **Step 10** under *Phase 4 — Improve reasoning and reliability* in [this book’s README](./README.md). After **planning** (Chapter 9) and **acting** (tools + retrieval), the agent should **check its own work** before the user trusts the answer.

---

## 1. What reflection means here

After each important step (or once before the final reply), the agent explicitly asks:

- Did the **retrieved** text actually support what I claimed?
- Do the **numbers** in my answer match **tool output** (not a different scenario)?
- What **assumptions** am I hiding (tax year, filing status, jurisdiction)?
- Does the answer **fully** address what the user asked (e.g. both “estimate” and “optimize next year”)?

This is not magic self-awareness—it is usually a **second LLM call** (or a small policy) with a fixed checklist and the **same evidence** the first pass had (tool logs, retrieved snippets).

---

## 2. Why it matters (especially in tax)

Failures are often **silent**:

- Wrong filing status or tax year
- Stale or generic rules instead of retrieved text
- Claiming a **401(k) “what-if”** without running a different tool call
- Citing **$X tax savings** that do not appear in any calculator output

Reflection turns “sounds plausible” into “**traceable** against tool outputs and retrieval.”

---

## 3. Three practical checks (from the tax-style demo)

| Check | Question |
|--------|-----------|
| **Evidence** | Is the answer grounded in retrieved IRS/policy-style text (or clearly labeled as general education)? |
| **Tool honesty** | If I cite a dollar amount or scenario, does it appear in `retrieve_tax_rules` / `baseline_tax_placeholder` outputs? |
| **Completeness** | Did I cover every part of the user’s goal (baseline + next-year angles if they asked for both)? |

---

## 4. How to implement in system design

- **Structured output**: reflection returns JSON (`issues[]`, booleans, short notes) so you can log it (Chapter 11).
- **Repair loop** (optional): if `issues_found` is non-empty, run one **revision** pass that must fix or disclaim each issue.
- **Cost/latency**: you can run a **light** critique on every turn, and a **heavy** critique only when tools ran or money figures appear.

---

## 5. Runnable demo

Script: [`code/ch10_reflection_tax_agent.py`](./code/ch10_reflection_tax_agent.py)

Pipeline (builds on Chapter 9):

1. **Phase 0** — OpenAI JSON session facts  
2. **Phase A** — Plan JSON  
3. **Phase B** — Tool loop + **tool trace** (name, args, output)  
4. **Phase C** — **Reflection JSON**: evidence / tool / completeness checks + **`final_answer`** (revised if needed)

**Not tax advice.** Stub tools only.

Run:

```bash
python code/ch10_reflection_tax_agent.py
python code/ch10_reflection_tax_agent.py 'I made $220k, married, 2 kids. What if I put $10k more in my 401(k)?'
```

Skip reflection (compare behavior):

```bash
python code/ch10_reflection_tax_agent.py --no-reflect "..."
```

(Or `cd code` and drop the `code/` prefix.)

---

## 6. What’s next

**Chapter 11** — Persist plans, tool traces, and reflection notes as **queryable traces** (local SQLite demo; same schema ideas port to cloud): [Logging and traces](./11-logging-and-traces.md) · [`code/ch11_logging_traces_tax_agent.py`](./code/ch11_logging_traces_tax_agent.py).

---

[← Chapter 9](./09-planning-before-execution.md) · [Book home](./README.md) · [Chapter 11 →](./11-logging-and-traces.md)
