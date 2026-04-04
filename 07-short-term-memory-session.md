# Chapter 7 — Short-term memory (session)

This chapter corresponds to **Step 7** under *Phase 3 — Make it useful* in [this book’s README](./README.md).

This chapter answers a practical question:

> “How do I make an agent stay coherent across multiple turns?”

In Chapter 6 you grounded the agent in **documents** (RAG). In Chapter 7 you ground it in **the conversation itself**.

---

## 1. What “short-term memory” actually is

Short-term memory is everything the agent uses to stay consistent **within one session**:

- **User facts** already stated (“married filing jointly”, “2 kids”, “income 220k”)
- **Intermediate results** (“scenario A tax estimate was $X”)
- **Open tasks / partial progress** (“we still need to compare Roth vs traditional”)
- **Decisions and constraints** (“assume 2025 standard deduction unless told otherwise”)

In code, this usually becomes one (or more) of:

- **Message history**: the simplest approach; you keep all messages and send them back each turn.
- **Working memory object**: a structured dict you maintain outside the model and inject each turn.
- **Rolling summary**: you keep the last N messages + a summary of earlier turns.
- **Hybrid**: summary + key-value facts + last few turns.

---

## 2. What problems it solves (and what it doesn’t)

### The three common failure modes

- **Forgets facts**: user told you income and filing status, agent asks again.
- **Contradicts itself**: produces two incompatible answers in the same session.
- **Loses the thread**: user asks a “what if …” and the agent forgets the baseline scenario.

### What short-term memory does *not* solve

- **Wrong knowledge**: memory doesn’t make rules correct; RAG does.
- **Cross-session personalization**: that’s Chapter 8 (long-term memory).
- **Security**: you still need to avoid storing secrets and PII unnecessarily.

---

## 3. A minimal session memory design (recommended starter)

For an educational agent, a very effective starter memory is:

- **`facts` (dict)**: stable user-provided facts you can reuse
- **`open_questions` (list)**: missing inputs you still need
- **`last_tool_results` (list)**: keep the last few tool outputs
- **`summary` (string)**: a compact summary of what has happened so far

Then, on every turn:

1. Append the user message to the transcript.
2. Update `facts/summary` from the new turn.
3. Call the model with:
   - system instruction
   - **memory injection** (facts + summary)
   - the last N messages
4. If the model calls tools, execute them, append tool results.
5. Produce an answer.

---

## 4. Memory injection pattern (the one thing you must do)

The key trick is to add a special message every turn that is *not* from the user:

```text
[MEMORY]
facts: …
summary: …
open_questions: …
```

This makes the “current state” explicit and easy for the model to use without rereading the entire chat.

---

## 5. System design: where short-term memory is stored

In real systems, “short-term memory” is usually not mystical — it’s just **session state** plus a **conversation log** stored somewhere reliable.

Common storage patterns:

- **In-process memory (single server)**
  - **What**: keep `facts/summary/transcript` in RAM (a Python dict) keyed by `session_id`.
  - **Pros**: simplest, fastest.
  - **Cons**: breaks on restarts, doesn’t scale horizontally, hard to share across workers.
  - **When**: demos, prototypes, single-user tools.

- **Server-side session store (Redis is the default)**
  - **What**: store short JSON blobs (`facts`, `summary`, `open_questions`) in Redis with TTL.
  - **Pros**: fast, shared across multiple app instances, easy expiration.
  - **Cons**: you still need a transcript store (or accept losing detailed history), and you must handle PII/retention.
  - **When**: production chat apps; “session” = minutes to hours.

- **Database event log (Postgres) + derived memory**
  - **What**: append every message/tool call to a `conversation_events` table; derive `summary/facts` as a cached projection.
  - **Pros**: auditable, replayable, reliable; good for debugging and compliance.
  - **Cons**: higher latency if you recompute too often; you usually add caching.
  - **When**: serious products; you want observability and reproducibility.

- **Hybrid: Postgres transcript + Redis working memory**
  - **What**: Postgres for the canonical log; Redis for the hot working set (summary, facts, last N turns).
  - **Pros**: common “best of both”; fast + durable.
  - **Cons**: more moving pieces; need consistency strategy (write-through / refresh).

- **Client-side memory (browser / app)**
  - **What**: the client sends the last N turns (or a summary) each request.
  - **Pros**: easy backend; user controls retention.
  - **Cons**: easy to tamper with; limited size; privacy depends on client security; not great for tool auditing.
  - **When**: lightweight apps, privacy-forward designs, offline-ish flows.

Operational details that matter:

- **Keying**: everything is keyed by `user_id` + `session_id` (not by free-form chat title).
- **TTL/retention**: short-term memory usually has an explicit TTL (hours/days).
- **Redaction**: store structured facts but avoid secrets/PII; consider hashing or encryption-at-rest for sensitive fields.
- **Concurrency**: two requests in the same session can race; use optimistic concurrency (version field) or per-session locking.

---

## 6. Demo code: a tiny multi-turn agent with session memory

Runnable script:

- `code/ch07_short_term_memory_agent.py`

It supports:

- multi-turn REPL (type multiple user messages)
- a simple `search_tax_corpus` tool (RAG over your local index)
- session memory (facts + summary + open questions)
- tool-calling loop (like Chapter 3/4), but across *multiple user turns*

Run it:

From the repository root:

```bash
python code/ch07_short_term_memory_agent.py
```

Or: `cd code` then `python ch07_short_term_memory_agent.py`.

Try this conversation:

```text
My income is 220k, married, 2 kids.
What filing statuses does the IRS describe?
Ok, now answer again but compare to my situation.
```

You should see that it **doesn’t ask again** for the facts you already gave, and it can use retrieval when needed.

---

## 7. Practical guidance (what to do in real products)

- **Cap memory**: keep last N turns + summary; don’t send unlimited history.
- **Prefer structured facts**: store “filing_status=MFJ”, not a paragraph.
- **Distinguish “user said” vs “model inferred”**: only persist stable user-provided facts.
- **Be explicit about assumptions**: store assumptions in memory (tax year, jurisdiction, etc.).
- **Don’t store secrets**: redact or refuse to store keys, SSNs, account numbers, etc.

---

## 8. What’s next

- **Chapter 8**: long-term memory (cross-session), and how to do it safely.
- Combine **RAG + short-term memory** for “what-if” scenario analysis without repeating inputs.

---

[← Chapter 6](./06-retrieval-and-rag.md) · [Book home](./README.md) · [Chapter 8 →](./08-long-term-memory-across-sessions.md) · [Runnable demo](./code/ch07_short_term_memory_agent.py)
