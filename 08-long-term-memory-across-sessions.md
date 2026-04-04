# Chapter 8 — Long-term memory (across sessions)

This chapter corresponds to **Step 8** under *Phase 3 — Make it useful* in [this book’s README](./README.md). It builds on [Chapter 7 — Short-term memory](./07-short-term-memory-session.md).

Short-term memory (Chapter 7) keeps one conversation coherent.

Long-term memory answers a different product question:

> “How does the agent get better over time without becoming creepy or wrong?”

This chapter focuses on **safe, useful, explicit** memory across sessions.

---

## 1. What long-term memory is (and isn’t)

Long-term memory is **durable state** associated with a user (or account) across sessions:

- **Preferences**: “keep answers short”, “be conservative”, “prefer bullets”
- **Recurring facts**: “married”, “2 kids”, “income range 200–250k”
- **Decisions**: “we chose Roth”, “we assume 2025 tax year unless specified”

It is *not*:

- a dump of the whole transcript forever
- “the model remembers everything” (it doesn’t)
- a substitute for RAG grounding

---

## 2. The core failure mode: stored hallucinations

Long-term memory can silently make your product worse:

- The model guesses a “fact”
- You store it
- Next session it becomes “truth”

So the key rule is:

> Only store things that are **useful**, **stable**, and **user-verified**.

Practical guardrails:

- **Allowlist** memory types (only certain fields can be stored)
- **Require explicit consent** before writing
- **Store provenance** (“user said”, timestamp, source message id)
- **Support edit/delete** (“forget that”, “update my preference”)

---

## 3. What to store (a simple schema)

Start with a tiny user profile:

- `preferences`
  - `style`: short / detailed
  - `risk_posture`: conservative / aggressive
  - `citation_preference`: always cite / only when asked
- `recurring_facts`
  - `marital_status`
  - `num_children`
  - `income_range_usd` (range, not exact)
- `notes`
  - short free-text notes that are *user-approved*

Avoid storing:

- secrets (API keys), account numbers, SSNs
- raw tool outputs or full PDFs
- medical/biometric data unless you have a real compliance program

---

## 4. System design: where teams store long-term memory

Many teams start **local** and move to managed storage (for example **AWS**) when they ship. Here is a practical progression:

### Local now (effective and simple)

- **Local JSON per user** (recommended starting point)
  - **What**: `profiles/<user_id>.json`
  - **Pros**: dead simple, easy to inspect/edit/delete, great for learning
  - **Key improvement**: write atomically (write temp file then replace) so you don’t corrupt profiles on crash
  - **Limits**: doesn’t scale across multiple servers; concurrent writes need locking/versioning

- **Local SQLite** (next step if you want stronger correctness)
  - **What**: a `user_profiles` table (`user_id`, `profile_json`, `updated_at`, `schema_version`)
  - **Pros**: transactions + concurrency; still one local file
  - **When**: you want “local but safer” and you’re doing more than a demo

### Production later (common patterns)

- **DynamoDB “user_profile” item** (AWS-friendly default)
  - **What**: one item per user: `PK=user_id`, `profile` (Map), `updated_at`, `schema_version`
  - **Pros**: low-latency, scales easily, simple access pattern (“get profile, update profile”)
  - **Add**: optimistic concurrency (a `version` field + conditional update)

- **Postgres “user_profile” table** (most common outside pure serverless)
  - **Pros**: durable, queryable (JSONB), easy reporting and backups

- **Redis is not long-term memory**
  - Redis is usually for short-term session state (TTL), not durable user memory.

- **Event-sourced profile** (best for audit/debugging)
  - Append “memory events” (`ADD_PREFERENCE`, `FORGET_FACT`) and compute the current profile.
  - Great for auditability and debugging.

Security basics:

- encrypt at rest for sensitive fields (if applicable)
- limit access (least privilege)
- add retention policies and deletion workflows

---

## 5. How to *use* long-term memory (in prompts)

Long-term memory is most effective when injected as a small, structured block:

```text
[USER_PROFILE]
preferences: …
recurring_facts: …
```

Then the model uses it to:

- tailor the response style
- reduce repeated questions
- interpret “do it again” requests

But it should still:

- cite sources for tax rules (RAG)
- ask clarifying questions when needed

---

## 6. Demo code: a tiny “profile memory” agent (persisted)

Runnable script:

- `code/ch08_long_term_memory_agent.py`

What it demonstrates (local-first, AWS-ready later):

- a persistent per-user JSON profile on disk (`code/profiles/<user>.json`)
- allowlisted fields only
- explicit “save this” / “forget this” commands
- profile injection into the model

Run it:

From the repository root:

```bash
python code/ch08_long_term_memory_agent.py --user demo
```

Or: `cd code` then `python ch08_long_term_memory_agent.py --user demo`. Use any profile name; files live under `code/profiles/`.

Try:

```text
remember: I prefer short answers.
remember: I have 2 kids.
What filing statuses does the IRS describe?
forget: num_children
```

---

## 7. Next steps

- Combine Chapter 6 (RAG) + Chapter 7 (session) + Chapter 8 (profile) into one “tax planning assistant”.
- Add a review UI: show proposed memory writes and let the user accept/reject.

---

[← Chapter 7](./07-short-term-memory-session.md) · [Book home](./README.md) · [Chapter 9 →](./09-planning-before-execution.md) · [Runnable demo](./code/ch08_long_term_memory_agent.py)
