# Chapter 16 — Evaluation and benchmarks

This chapter corresponds to **Step 16** under *Phase 7 — Productionize it* in [this book’s README](./README.md). If you cannot **repeat** a test suite, you cannot tell whether a change helped or regressed.

---

## 1. What to measure

* **Success rate** — task completed vs failed (define “success” per task).
* **Tool accuracy** — correct tool? correct args? (needs traces from Ch 11-style logging).
* **Latency** — wall time per task and p95 across runs.
* **Cost** — tokens × price (use provider dashboards for truth).
* **Failure modes** — log categories: timeout, bad JSON, wrong tool, user abandonment.

---

## 2. Runnable demo

Script: [`code/ch16_agent_eval_demo.py`](./code/ch16_agent_eval_demo.py)

Small fixed **task set** over [Chapter 12](./12-specialized-agents-narrow-tools.md) agents. Each task checks a **substring** in the final answer (cheap oracle for teaching).

```bash
cd code
python ch16_agent_eval_demo.py list
python ch16_agent_eval_demo.py run
python ch16_agent_eval_demo.py run --agent research
```

Output is **JSON**: pass rate, timings per task. Extend `DEFAULT_TASKS` in the script as you grow.

---

## 3. What’s next

**Chapter 17** — latency and cost tricks: [Optimize](./17-latency-cost-optimization.md).

---

[← Chapter 15](./15-tool-layer-security.md) · [Book home](./README.md) · [Chapter 17 →](./17-latency-cost-optimization.md)
