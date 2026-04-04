# Chapter 9 — Planning before execution

This chapter corresponds to **Step 9** under *Phase 4 — Improve reasoning and reliability* in [this book’s README](./README.md). Phase 4 starts here: make the agent **less fragile** on longer tasks.

This chapter answers:

> “How do I stop the agent from jumping straight to an answer when the task needs several steps?”

---

## 1. What planning means for agents

**Planning** is an explicit step where the model (or a separate planner) outputs **ordered subgoals** before heavy tool use or long answers.

Typical pattern for a tax-style request:

```text
1. Identify filing status, income, deductions, and goals
2. Retrieve relevant federal tax rules for the tax year
3. Run a baseline estimate (or ask for missing inputs)
4. Generate alternative scenarios (401(k), Roth vs traditional, itemized vs standard)
5. Compare results
6. Summarize recommendations with caveats
```

This is not “more clever prompting” only—it is **structure**: the agent commits to a checklist before it acts.

---

## 2. Why planning helps

Without planning, agents often:

- start **calculating or advising** before they have **facts** (filing status, year, jurisdiction)
- **skip retrieval** and answer from general knowledge
- answer **optimization** (“reduce taxes next year”) before establishing a **baseline**
- **wander** across subtopics in one long reply

With planning, you get:

- visible **missing information** early
- a **trace** you can log (“step 3 failed because …”)
- a hook for **re-planning** after each major tool result (Chapter 10 adds critique)

---

## 3. Common implementation patterns

### Plan-then-execute (two-phase)

1. **Plan call**: model returns structured plan (JSON is ideal): `steps[]`, `missing_information[]`, optional `assumptions[]`.
2. **Execute loop**: ReAct-style tool loop constrained by “follow the plan; mark steps done.”

Pros: simple to reason about, easy to log.  
Cons: plan can be stale if tool output changes the situation—then you **re-plan** (see below).

### Re-plan after each milestone

After retrieval or after a calculator returns, run a **short** “update plan” step: keep finished steps, adjust order, add new steps.

### When *not* to force planning

- Trivial one-shot Q&A (“what is 2+2?”)
- Already-short retrieval questions

Use a **router** or heuristic: long user message + multiple goals → plan; else answer directly.

---

## 4. System design notes

- Store the **approved plan** in session state (Chapter 7) alongside tool outputs.
- Log **plan version** and timestamps for debugging (Chapter 11).
- In production, separate **planner** and **executor** roles is common (see Phase 6 in [this book’s README](./README.md)).

---

## 5. Runnable demo (tax planning scenario)

Script: [`code/ch09_planning_tax_agent.py`](./code/ch09_planning_tax_agent.py)

It demonstrates:

1. **Phase 0 — Structured extraction (OpenAI only)**: one completion with `response_format` JSON. The model turns natural language into facts (`annual_income_usd`, `married`, `num_children`, `tax_year_focus_for_discussion`, etc.). There is **no regex fallback** in code—if you want different behavior, you adjust the extractor prompt or the model.
2. **Phase A — Planning**: one completion with `response_format` JSON: `steps`, `missing_information`, `rationale` (planner sees `[SESSION_FACTS_FROM_EXTRACTOR]` plus the raw user message).
3. **Phase B — Execution**: tool loop with **stub** tools (`retrieve_tax_rules`, `baseline_tax_placeholder`) so you can see the plan drive behavior without a real tax engine.

### Why it can look like “$220K” was not parsed

Usually **OpenAI is not the problem**—the **shell** is:

- **PowerShell** treats `$220K` inside **double-quoted** strings as a variable. The process often receives text like `I made , married` (the `$220K` part disappears), so the model correctly returns `annual_income_usd: null`.
- **Fix:** pass the user message in **single quotes** on PowerShell, or escape: `` `$220K ``.

If the string in Phase 0 truly contains `$220K` / `220k` but the model still returns `null`, check Phase 0 printed JSON and consider tightening the extractor prompt (the script now lists explicit normalization examples including `$220K`).

If the API returns malformed JSON, Phase 0 sets `extract_error` and all fact fields stay `null`.

**Not tax advice.** Numbers are illustrative placeholders only.

Run:

From the repository root:

```bash
python code/ch09_planning_tax_agent.py
python code/ch09_planning_tax_agent.py "I made $220k, married, 2 kids, and want to reduce taxes next year."
```

**PowerShell:** `$` starts a variable, so `"$220k"` may reach Python as empty. Use **single quotes** around the user message:

```powershell
python code/ch09_planning_tax_agent.py 'I made $220k, married, 2 kids, and want to reduce taxes next year.'
```

Optional: skip the planning phase to compare behavior:

```bash
python code/ch09_planning_tax_agent.py --no-plan "I made $220k, married, 2 kids..."
```

Or run the same commands after `cd code`.

---

## 6. What’s next

- **Chapter 10**: reflection / critique after each step (did retrieval match the year? did we run the scenario we claimed?).
- **Chapter 11**: structured logging and traces for plans + tool calls.

---

[← Chapter 8](./08-long-term-memory-across-sessions.md) · [Book home](./README.md) · [Chapter 10 →](./10-reflection-and-critique.md)
