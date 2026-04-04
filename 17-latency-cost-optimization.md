# Chapter 17 — Latency and cost optimization

This chapter corresponds to **Step 17** under *Phase 7 — Productionize it* in [this book’s README](./README.md). After you can **measure** (Chapter 16), you can **optimize** without guessing.

---

## 1. Common levers

| Technique | When it helps |
|-----------|----------------|
| **Caching** | Identical or near-identical queries (careful with personalization and staleness) |
| **Smaller / faster model for routing** | Cheap classification before an expensive multi-tool run |
| **Larger model only for hard steps** | Router sends “complex” tasks to a stronger model |
| **Parallel tool calls** | Independent sub-queries (when the API and safety model allow) |

---

## 2. Runnable demo

Script: [`code/ch17_latency_cost_demo.py`](./code/ch17_latency_cost_demo.py)

Three mini demos in one `run`:

1. **Cache** — second identical Ch12 `document` query hits an in-memory dict (no second agent run).
2. **Router** — short JSON `simple|complex` classification with **low `max_tokens`**.
3. **Parallel** — `asyncio.gather` on two short async completions.

```bash
cd code
python ch17_latency_cost_demo.py list
python ch17_latency_cost_demo.py run
```

Uses **`gpt-4o-mini`** for everything to keep spend small; swap models per step in production.

---

## 3. What’s next

**Chapter 18** — deploy and observability: [Observability](./18-deploy-observability.md).

---

[← Chapter 16](./16-evaluation-benchmarks.md) · [Book home](./README.md) · [Chapter 18 →](./18-deploy-observability.md)
