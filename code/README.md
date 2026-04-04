# Runnable examples (Chapters 1–18)

These scripts align with the numbered chapters in [the book README](../README.md). Most examples use **OpenAI** and load **`OPENAI_API_KEY`** via [`common.py`](./common.py): it reads **`code/.env` first**, then fills any missing variables from **`rag_federal_individual/.env`** (same order as the RAG CLI scripts). Chapter 2 in the book also shows Anthropic and Google patterns; this folder’s runnable demos are OpenAI-first for a single install path.

## Setup

```bash
cd code
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set your key:

```env
OPENAI_API_KEY=sk-...
```

## Run

`common.py` only loads `.env`; it is imported by the OpenAI scripts.

| Script | Chapter | Needs API key |
|--------|---------|---------------|
| `python ch01_tax_extraction.py` | 1 — Tax JSON + Pydantic + retries | Yes |
| `python ch02_country_extraction.py` | 2 — Country JSON extraction | Yes |
| `python ch03a_chatbot_one_shot.py` | 3 — Single-shot chatbot (no tools) | Yes |
| `python ch03b_agent_stub.py` | 3 — Agent loop with stub “model” | No |
| `python ch03c_agent_openai_tools.py` | 3 — Agent loop with real tool calls | Yes |
| `python ch04_city_coordinates_agent.py` | 4 — One tool: lat/long via SQLite cache, else Open-Meteo geocoding | Yes (OpenAI); geocoding HTTP has no API key |
| `python ch05_stop_conditions_demo.py` | 5 — Max iterations, bad tools, timeouts, fallbacks (no key) | No |
| `python ch05_stop_conditions_demo.py --openai` | 5 — Same + verbose OpenAI loop with cap | Yes |
| `python ch06_simple_rag_agent.py` | 6 — Minimal RAG agent (retrieve → answer; may retry once) | Yes |
| `python ch07_short_term_memory_agent.py` | 7 — Multi-turn agent with short-term memory + RAG tool | Yes |
| `python ch08_long_term_memory_agent.py --user you` | 8 — Long-term memory profile (persisted across runs) | Yes |
| `python ch09_planning_tax_agent.py` | 9 — Plan (JSON) then execute with stub tax tools | Yes |
| `python ch10_reflection_tax_agent.py` | 10 — Plan + execute + tool trace + reflection JSON (`--no-reflect` to skip) | Yes |
| `python ch11_logging_traces_tax_agent.py` | 11 — Same pipeline as 10, persists `runs`, `tool_calls`, `retrieval_events`, `reflections`, … to SQLite (`--list`, `--show`) | Yes |
| `python ch11_logging_traces_tax_agent.py --list` | 11 — List stored runs (no OpenAI call) | No |
| `python ch12_specialized_agents_demo.py list` | 12 — List three specialized agents and their tools (no key) | No |
| `python ch12_specialized_agents_demo.py research "..."` | 12 — Research agent (narrow stub tools) | Yes |
| `python ch12_specialized_agents_demo.py coding "..."` | 12 — Coding agent (allowlisted read + stub tests) | Yes |
| `python ch12_specialized_agents_demo.py document "..."` | 12 — Document QA agent (stub retrieval + report) | Yes |
| `python ch13_multi_agent_split_roles.py list` | 13 — Supervisor → worker → critic pipeline (explainer) | No |
| `python ch13_multi_agent_split_roles.py run "..."` | 13 — Ch12 worker chosen by supervisor JSON + critic | Yes |
| `python ch14_multi_agent_coordination.py list` | 14 — Coordination rules (tool permissions, state, retry) | No |
| `python ch14_multi_agent_coordination.py run "..."` | 14 — Shared state + reviewer JSON + optional retry / escalate | Yes |
| `python ch15_tool_security_demo.py list` | 15 — Tool security (heuristics + allowlisted `safe_multiply`) | No |
| `python ch15_tool_security_demo.py dry-run` | 15 — Same checks without OpenAI | No |
| `python ch15_tool_security_demo.py run "..."` | 15 — Tiny agent with bounded multiply tool | Yes |
| `python ch16_agent_eval_demo.py list` | 16 — Task set for eval (Ch12 agents) | No |
| `python ch16_agent_eval_demo.py run` | 16 — Run benchmark + JSON summary | Yes |
| `python ch17_latency_cost_demo.py list` | 17 — Cache, router, parallel completions (explainer) | No |
| `python ch17_latency_cost_demo.py run` | 17 — Demo latency/cost patterns | Yes |
| `python ch18_observability_demo.py list` | 18 — Traces on stderr, retries, prompt version | No |
| `python ch18_observability_demo.py run` | 18 — One completion + JSON trace lines | Yes |

**Chapter 4** creates `ch04_city_coords.sqlite` (ignored via `code/ch04_*.sqlite` in the repo root `.gitignore`); delete it to reset the geocode cache. **Chapter 11** creates `ch11_agent_traces.sqlite` (ignored via `code/ch11_*.sqlite`). For math-only questions the model usually skips the tool (`tool_choice=auto`); try `python ch04_city_coordinates_agent.py "What is 15 + 27?"`.

**Suggested order:** run `ch03b_agent_stub.py` first (offline), then `ch03a` vs `ch03c` to compare one-shot vs tool loop on the same math question.

Do not commit `.env`; it is listed in the repository root `.gitignore`.
