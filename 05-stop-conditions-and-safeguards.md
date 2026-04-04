# Chapter 5 — Stop conditions and safeguards

This chapter corresponds to **Step 5** under *Phase 2 — Build your first real agent* in [this book’s README](./README.md). It assumes you have a working tool loop from [Chapter 4](./04-city-coordinates-cache-open-meteo.md) and [`code/ch04_city_coordinates_agent.py`](./code/ch04_city_coordinates_agent.py).

**Problem.** A tool-calling agent can **fail open**: the model may request tools forever, invent tool names, pass malformed arguments, or drive HTTP calls that hang. Your **orchestrator** must bound work and return something intelligible to the user.

**Deliverable.** An agent that **always exits**: capped iterations, safe handling of unknown or bad tools, timeouts on I/O, and a **fallback** message when you give up.

---

## 1. Max iterations (hard cap on the loop)

Every agent loop should have **`max_steps`** (or equivalent): a maximum number of *model* turns or *tool* rounds. Without it, a buggy model or a bad prompt can loop until you hit API limits, cost spikes, or a hung client.

**What to count.** Be explicit: some teams cap **LLM calls**, others cap **tool executions**; they differ if one assistant message batches several tool calls. Pick one policy and log it.

**Fallback.** When the cap is reached, do not leave the user with silence. Return a short, honest message (for example: “Stopped after N steps; here is what we know so far …”) and optionally log the last state for debugging.

**Reference.** Same structural idea as bounded recursion in any event loop; OpenAI discussions of rate limits and retries are adjacent operational concerns ([OpenAI: error codes](https://platform.openai.com/docs/guides/error-codes)).

---

## 2. Invalid tool calls (unknown name, bad arguments)

The model may emit:

- A **tool name** that is not in your registry.  
- **Arguments** that do not match your Python signature (missing keys, wrong types).

**Policy.**

- **Unknown tool:** append a tool message whose `content` is a clear error string, for example `error: unknown tool 'foo'`. The model may recover on the next turn; alternatively you can abort immediately depending on risk.  
- **Bad arguments:** catch `TypeError` / validation errors in your dispatcher; return `error: bad arguments: …` as the observation. Never `eval` or execute dynamic code based on unchecked model strings.

This mirrors the “trust boundary” theme from [Chapter 1](./01-llms-at-a-practical-level.md): the model proposes; your code enforces.

---

## 3. Timeout handling (HTTP and other I/O)

Any tool that does **network I/O** should use explicit **timeouts**. Defaults that wait minutes are dangerous in an agent loop where each step may trigger multiple calls.

In Python, clients like **httpx** or **requests** take a `timeout=` argument. On timeout, catch the exception and convert it to a **short string** for the tool result so the model (or your fallback path) can react.

**References.** [httpx — Timeouts](https://www.python-httpx.org/advanced/timeouts/); [OpenAI: error codes](https://platform.openai.com/docs/guides/error-codes) for API-side timeouts and retries at the SDK layer.

---

## 4. Fallback responses (user-visible outcome)

A **fallback** is what the user sees when you stop without a normal final model answer: max steps exceeded, repeated tool errors, or a policy decision to abort.

Good fallbacks:

- State **why** in one line (stopped after N steps; service timed out).  
- Optionally include **partial** information (last successful tool output).  
- **Log** the full trace server-side for engineers.

Avoid dumping raw stack traces to end users in production.

---

## 5. Runnable demo (no API key for most of it)

[`code/ch05_stop_conditions_demo.py`](./code/ch05_stop_conditions_demo.py) walks through:

1. **Stub loop** that always issues another tool call → **max_steps** → printed **FALLBACK**.  
2. **Unknown tool** → error string returned to the “model” channel.  
3. **Geocoding** with an impossibly small timeout → timeout → error string.  
4. With `--openai` and **`OPENAI_API_KEY`**, a **verbose** capped loop using **`get_city_coordinates`** from Chapter 4.

```bash
python ch05_stop_conditions_demo.py
python ch05_stop_conditions_demo.py --openai
```

---

## 6. How this connects to Chapter 4

[`ch04_city_coordinates_agent.py`](./code/ch04_city_coordinates_agent.py) already uses **`max_steps`** and dispatches only known tools with try/except on arguments. Chapter 5 makes those behaviors **explicit requirements** and adds **timeouts** on HTTP inside tools (recommended next change in your own fork of the geocode helper) and **user-visible fallbacks** when the cap triggers.

---

## 7. Suggested reading order

1. [OpenAI — Error codes](https://platform.openai.com/docs/guides/error-codes)  
2. [httpx — Timeouts](https://www.python-httpx.org/advanced/timeouts/)  
3. [Chapter 3 — Chatbot vs agent](./03-chatbot-vs-agent-and-the-loop.md) (loop structure)  
4. [Chapter 4 — City coordinates](./04-city-coordinates-cache-open-meteo.md)  

---

[← Chapter 4](./04-city-coordinates-cache-open-meteo.md) · [Book home](./README.md) · [Chapter 6 →](./06-retrieval-and-rag.md) · [Demo script](./code/ch05_stop_conditions_demo.py)
