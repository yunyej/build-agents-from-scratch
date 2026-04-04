# Chapter 18 — Deploy with observability

This chapter corresponds to **Step 18** under *Phase 7 — Productionize it* in [this book’s README](./README.md). Shipping means you can **see** failures, **retry** sensibly, and tie behavior to **prompt / model versions**.

---

## 1. Building blocks

* **Traces** — request id, spans per LLM call and tool (aligns with [Chapter 11](./11-logging-and-traces.md)).
* **Metrics** — latency, error rate, token usage, queue depth for async jobs.
* **Retries** — exponential backoff on transient API errors (not on 4xx content errors).
* **Alerting** — SLO breaches, error spikes, stuck jobs.
* **Versioned prompts** — `PROMPT_VERSION` or git SHA in every log line and config.

---

## 2. Runnable demo

Script: [`code/ch18_observability_demo.py`](./code/ch18_observability_demo.py)

- **`trace_event`** — prints **JSON lines to stderr** (`event`, `prompt_version`, …).
- **`with_retries`** — wraps one completion; retries on connection / timeout / rate limit.
- **`PROMPT_VERSION`** — constant passed through trace metadata.

```bash
cd code
python ch18_observability_demo.py list
python ch18_observability_demo.py run
```

Stdout: model answer. Stderr: trace lines (redirect to a file or log agent in production).

---

## 3. What’s next

You now have a full arc from single-tool agents through multi-agent coordination and production hygiene. When you build a client-facing service, optional companion material in the parent monorepo is listed under [Further reading outside this book](./README.md#further-reading-outside-this-book) (*tax_calculator_demo*, *PRODUCT_STRUCTURE_AWS*).

---

[← Chapter 17](./17-latency-cost-optimization.md) · [Book home](./README.md)
