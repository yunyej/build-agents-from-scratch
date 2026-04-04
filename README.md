# What an agent actually is

Short chapters that build from **LLM basics** to **production-minded agents**: the agent loop, tools, retrieval, memory, planning, multi-agent coordination, and hardening (security, evaluation, cost, observability).

**Using this folder as its own repository.** This directory is meant to work as the **root of a standalone Git repo**: chapters live here alongside [`code/`](./code/README.md) (runnable demos) and [`rag_federal_individual/`](./rag_federal_individual/README.md) (sample corpus pipeline). All in-repo links assume that layout.

## Author and disclaimer

**Author:** Yunye Jiang · University of Pennsylvania · [LinkedIn](https://www.linkedin.com/in/yunye-jiang)

This project is **personal study notes** for learning how LLMs and agents work. It is shared **for education only**. The author **does not warrant** accuracy or completeness and **assumes no responsibility or liability** for errors, omissions, or any use you make of this material. Scenarios involving tax, law, or products are **illustrative**; rely on official sources and professional advice where stakes are high. **References** (vendor documentation, papers, and links) are cited in the chapters themselves and remain the authoritative sources for APIs, limits, and research claims.

If you run the code locally, keep **API keys** in `code/.env` (or `rag_federal_individual/.env`) and **never commit** them.

**License:** [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](./LICENSE). You may **view, share, and adapt** this work for **non-commercial** purposes with **attribution**. **Commercial use** (e.g. in a paid product or service, or primarily for commercial advantage) is **not** granted by this license; for that, contact the author. **Third-party** material (quoted text, linked government pages, vendor docs) stays under its **original** terms.

## Chapters in this book

1. [Chapter 1 — LLMs at a practical level](./01-llms-at-a-practical-level.md)
2. [Chapter 2 — API usage (OpenAI, Anthropic, Google)](./02-api-usage-three-providers.md)
3. [Chapter 3 — Chatbot vs agent and the loop](./03-chatbot-vs-agent-and-the-loop.md)
4. [Chapter 4 — City coordinates: cache + Open-Meteo](./04-city-coordinates-cache-open-meteo.md)
5. [Chapter 5 — Stop conditions and safeguards](./05-stop-conditions-and-safeguards.md)
6. [Chapter 6 — Retrieval and RAG](./06-retrieval-and-rag.md)
7. [Chapter 7 — Short-term memory (session)](./07-short-term-memory-session.md)
8. [Chapter 8 — Long-term memory (across sessions)](./08-long-term-memory-across-sessions.md)
9. [Chapter 9 — Planning before execution](./09-planning-before-execution.md)
10. [Chapter 10 — Reflection and critique](./10-reflection-and-critique.md)
11. [Chapter 11 — Logging and traces](./11-logging-and-traces.md)
12. [Chapter 12 — Specialized agents and narrow toolsets](./12-specialized-agents-narrow-tools.md)
13. [Chapter 13 — Multi-agent: split roles](./13-multi-agent-split-roles.md)
14. [Chapter 14 — Multi-agent: coordination rules](./14-multi-agent-coordination-rules.md)
15. [Chapter 15 — Secure the tool layer](./15-tool-layer-security.md)
16. [Chapter 16 — Evaluation and benchmarks](./16-evaluation-benchmarks.md)
17. [Chapter 17 — Latency and cost optimization](./17-latency-cost-optimization.md)
18. [Chapter 18 — Deploy with observability](./18-deploy-observability.md)

**Runnable Python (OpenAI + `.env`):** [`code/README.md`](./code/README.md)

**Federal individual corpus (ingest/chunk, separate folder):** [`rag_federal_individual/`](./rag_federal_individual/README.md)

---

# Phase 1 — Learn the minimum foundations

Goal: understand what an agent actually is.

## Step 1: Learn how LLMs work at a practical level

You should be comfortable with:

* tokens and context windows
* temperature and sampling
* prompting basics
* structured output / JSON output
* why models hallucinate
* why “reasoning” is not the same as “truth”

Deliverable:

* build a few simple prompts that reliably produce structured JSON

**Chapter (full notes + references):** [Chapter 1 — LLMs at a practical level](./01-llms-at-a-practical-level.md)

## Step 2: Learn API usage for an LLM

You need to know how to:

* send messages to a model
* define system and user prompts
* parse outputs
* handle failures and malformed JSON

Deliverable:

* a small script that sends a task and gets back valid structured data

**Chapter (full notes + references + three providers):** [Chapter 2 — API usage (OpenAI, Anthropic, Google)](./02-api-usage-three-providers.md)

## Step 3: Understand what makes an agent different from a chatbot

A chatbot answers.
An agent:

* decides what to do
* uses tools
* keeps track of state
* loops until done

Deliverable:

* write down the basic loop:
  observe → think → act → observe → stop

**Chapter (full notes + references + runnable stub loop):** [Chapter 3 — Chatbot vs agent and the loop](./03-chatbot-vs-agent-and-the-loop.md)

---

# Phase 2 — Build your first real agent

Goal: create a tiny working agent with tools.

## Step 4: Add one simple tool and implement the agent loop

Start with one tool only:

* calculator
* weather API
* web search
* database lookup
* Python function

The model should decide:

* whether to call the tool
* what arguments to pass
* how to use the result

**Implement the loop** (ReAct-style with tool calling: action = tool call, observation = tool message):

1. read user request
2. ask model what to do
3. execute tool if needed
4. append result to state
5. ask model again
6. stop when final answer is ready

Deliverables:

* an agent that answers some questions directly and uses the tool when needed
* a ReAct-style single-agent loop

**Chapter (one tool: coordinates, DB first then online):** [Chapter 4 — City coordinates: cache + Open-Meteo](./04-city-coordinates-cache-open-meteo.md)

**Runnable:** [`code/ch04_city_coordinates_agent.py`](./code/ch04_city_coordinates_agent.py) follows the numbered loop above (`tool_choice="auto"`).

## Step 5: Add stop conditions and safeguards

Your agent must not loop forever.

Add:

* max iterations
* invalid tool call handling
* timeout handling
* fallback responses

Deliverable:

* agent exits cleanly even when the model makes mistakes

**Chapter (notes + references + demo map):** [Chapter 5 — Stop conditions and safeguards](./05-stop-conditions-and-safeguards.md)

**Live demo:** [`code/ch05_stop_conditions_demo.py`](./code/ch05_stop_conditions_demo.py) (add `--openai` for the capped verbose loop; needs `OPENAI_API_KEY`).

---

# Phase 3 — Make it useful

Goal: build an agent people would actually use.

## Step 6: Add retrieval (RAG)

Teach the agent to look up information from documents.

Learn:

* chunking
* embeddings
* vector search
* retrieval quality
* grounding answers in sources

Deliverable:

* an agent that can answer questions over a small document set

**Chapter + corpus:** [Chapter 6 — Retrieval and RAG](./06-retrieval-and-rag.md) · scripts in [`rag_federal_individual/`](./rag_federal_individual/README.md)

## Step 7: Add short-term memory

The agent should remember:

* prior user goals
* tool outputs from this session
* partial progress

Deliverable:

* multi-turn agent that stays consistent within one conversation

**Chapter + runnable:** [Chapter 7 — Short-term memory (session)](./07-short-term-memory-session.md) · [`code/ch07_short_term_memory_agent.py`](./code/ch07_short_term_memory_agent.py)

## Step 8: Add long-term memory carefully

Store only useful things:

* preferences
* recurring facts
* previous tasks
* prior decisions

Deliverable:

* agent that improves over repeated usage without becoming messy

**Chapter + runnable:** [Chapter 8 — Long-term memory (across sessions)](./08-long-term-memory-across-sessions.md) · [`code/ch08_long_term_memory_agent.py`](./code/ch08_long_term_memory_agent.py)

---

# Phase 4 — Improve reasoning and reliability

Goal: make the agent less fragile.

## Step 9: Add planning

Before acting, the agent should sometimes produce a plan.

Useful patterns:

* plan first, then execute
* decompose big tasks into substeps
* revise plan after each step

Deliverable:

* agent can handle longer tasks without wandering

**Chapter + runnable:** [Chapter 9 — Planning before execution](./09-planning-before-execution.md) · [`code/ch09_planning_tax_agent.py`](./code/ch09_planning_tax_agent.py)

## Step 10: Add reflection or critique

Have the agent check:

* did the tool output answer the question?
* is anything missing?
* does the final response match evidence?

Deliverable:

* fewer bad final answers from shallow reasoning

**Chapter + runnable:** [Chapter 10 — Reflection and critique](./10-reflection-and-critique.md) · [`code/ch10_reflection_tax_agent.py`](./code/ch10_reflection_tax_agent.py)

## Step 11: Add logging and traces

You need visibility into:

* prompts
* tool calls
* outputs
* errors
* total steps

Deliverable:

* you can inspect exactly why the agent failed

**Chapter (local SQLite vs cloud + runnable demo):** [Chapter 11 — Logging and traces](./11-logging-and-traces.md) · [`code/ch11_logging_traces_tax_agent.py`](./code/ch11_logging_traces_tax_agent.py)

**Consolidated product-style demo (Ch 9–11 in one package):** see [Further reading outside this book](#further-reading-outside-this-book) (*tax_calculator_demo* in the parent monorepo, if you have it).

---

# Phase 5 — Build specialized agents

Goal: create agents for real workflows.

## Step 12: Specialized agents and narrow toolsets

Build **several small agents**, not one universal assistant — and give **each** a **small, role-specific** toolset.

Good starter choices:

* **Research agent:** web search (or RAG), excerpt / clip, citation formatter
* **Coding agent:** repo reader, safe code or test runner, small calculator
* **Document QA agent:** retrieval, extraction, structured reporting

This teaches specialization and **cleaner debugging** better than one agent with every tool enabled.

Deliverable:

* three focused agents with **clear boundaries** and **non-overlapping** tools (as much as practical)

**Chapter + runnable:** [Chapter 12 — Specialized agents and narrow toolsets](./12-specialized-agents-narrow-tools.md) · [`code/ch12_specialized_agents_demo.py`](./code/ch12_specialized_agents_demo.py)

**Product-scale role split (policy / household / RAG):** see [Further reading outside this book](#further-reading-outside-this-book) (*multi_agent_plan* in the parent monorepo, if you have it).

---

# Phase 6 — Learn multi-agent design

Goal: coordinate specialized roles.

## Step 13: Split roles

A good first multi-agent pattern:

* planner
* executor
* critic

Or:

* researcher
* writer
* reviewer

Deliverable:

* a simple supervisor-worker system

**Chapter + runnable:** [Chapter 13 — Multi-agent: split roles](./13-multi-agent-split-roles.md) · [`code/ch13_multi_agent_split_roles.py`](./code/ch13_multi_agent_split_roles.py)

## Step 14: Add coordination rules

Decide:

* who is allowed to call tools
* who approves final output
* how agents share memory
* when escalation happens

Deliverable:

* multi-agent system that does not become chaotic

**Chapter + runnable:** [Chapter 14 — Multi-agent: coordination rules](./14-multi-agent-coordination-rules.md) · [`code/ch14_multi_agent_coordination.py`](./code/ch14_multi_agent_coordination.py)

---

# Phase 7 — Productionize it

Goal: move from demo to reliable system.

## Step 15: Secure the tool layer

You must defend against:

* prompt injection
* malicious tool arguments
* unsafe code execution
* data leakage

Deliverable:

* tool permission checks and sanitization

**Chapter + runnable:** [Chapter 15 — Secure the tool layer](./15-tool-layer-security.md) · [`code/ch15_tool_security_demo.py`](./code/ch15_tool_security_demo.py)

## Step 16: Add evaluation

Create a test set of tasks and measure:

* success rate
* tool call accuracy
* latency
* cost
* failure modes

Deliverable:

* repeatable benchmark for your agent

**Chapter + runnable:** [Chapter 16 — Evaluation and benchmarks](./16-evaluation-benchmarks.md) · [`code/ch16_agent_eval_demo.py`](./code/ch16_agent_eval_demo.py)

## Step 17: Optimize latency and cost

Add:

* caching
* smaller model for routing
* larger model only for complex reasoning
* parallel tool calls where safe

Deliverable:

* cheaper, faster agent

**Chapter + runnable:** [Chapter 17 — Latency and cost optimization](./17-latency-cost-optimization.md) · [`code/ch17_latency_cost_demo.py`](./code/ch17_latency_cost_demo.py)

## Step 18: Deploy with observability

Use:

* traces
* metrics
* retries
* alerting
* versioned prompts

Deliverable:

* production-ready service you can maintain

**Chapter + runnable:** [Chapter 18 — Deploy with observability](./18-deploy-observability.md) · [`code/ch18_observability_demo.py`](./code/ch18_observability_demo.py)

---

# Best learning order

Do these in this order:

1. LLM API basics
2. structured output
3. one-tool agent + agent loop
4. RAG
5. memory
6. planning
7. reflection
8. specialized agents
9. multi-agent
10. evals
11. production hardening

---

# What to build at each level

## Level 1: beginner

Build:

* calculator/tool agent
* FAQ agent over documents

Skills learned:

* prompting
* tool calling
* loop control
* RAG basics

## Level 2: intermediate

Build:

* research agent with search + summarization
* coding agent with code execution
* task planner agent

Skills learned:

* planning
* memory
* retries
* trace inspection

## Level 3: advanced

Build:

* multi-agent workflow
* long-running task agent
* production API service with monitoring

Skills learned:

* orchestration
* safety
* evaluation
* scalability

---

# Common mistakes to avoid

* building multi-agent systems too early
* adding too many tools at once
* skipping logging
* trusting model output without validation
* storing too much memory
* building “general intelligence” instead of a narrow useful workflow

---

## Further reading outside this book

If you cloned **only** this repository, the paths below are not present; they refer to optional material in the larger **agent_infra** monorepo this book was extracted from.

| Topic | Where (sibling of this folder when the monorepo is checked out) |
|--------|------------------------------------------------------------------|
| Original phased outline | `background/to_learn.md` |
| Consolidated tax-style demo (Chapters 9–11) | `tax_calculator_demo/README.md` |
| Product-scale multi-agent architecture | `multi_agent_plan/multi_agent_plan`, `multi_agent_plan/PRODUCT_STRUCTURE_AWS.md` |

---