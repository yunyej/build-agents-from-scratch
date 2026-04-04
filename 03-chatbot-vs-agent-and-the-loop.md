# Chapter 3 — Chatbot vs agent and the loop

This chapter corresponds to **Step 3** under *Phase 1 — Learn the minimum foundations* in [this book’s README](./README.md). It builds on [Chapter 1](./01-llms-at-a-practical-level.md) (how LLMs behave) and [Chapter 2](./02-api-usage-three-providers.md) (how you call an API).

**Deliverable.** You can write down—and recognize in code—the basic loop: **observe → think → act → observe → … → stop**, and explain why a **chatbot** is only the special case of a single turn (or a single model call) without tools.

**Runnable companions.** Offline loop (no API key): [`code/ch03b_agent_stub.py`](./code/ch03b_agent_stub.py). With OpenAI: single-shot [`code/ch03a_chatbot_one_shot.py`](./code/ch03a_chatbot_one_shot.py) vs tool loop [`code/ch03c_agent_openai_tools.py`](./code/ch03c_agent_openai_tools.py). Setup: [`code/README.md`](./code/README.md).

---

## 1. Two ways to use a model

**Chatbot (narrow sense).** The system sends a prompt (and maybe history) to the model once, or follows a fixed pattern of turns where the model **never** executes anything outside the chat transcript. The only “action” is emitting the next assistant message. Useful for Q&A, drafting, and conversation when no external system must be updated.

**Agent.** A **program** wraps the model in a **loop**. The model can request **tools** (functions, HTTP calls, database queries, simulators). The **runtime** executes those tools, appends the results to **state**, and calls the model again. The loop stops when the model produces a **final** answer or when a guardrail fires (max steps, timeout, human approval). The model **decides** what to do next; the code **enforces** what is allowed.

The same underlying LLM can power both patterns. The difference is **orchestration**, not the weights.

---

## 2. State: what “observe” means

**State** is everything the model may see on the next step. It usually includes:

- The **user goal** and conversation history  
- **System instructions** (persona, safety, tool list)  
- **Tool outputs** from earlier iterations (observations)  
- Optional **scratchpad** (chain-of-thought, plan)—if you store it at all  

Agents exhaust **context windows** faster than single-shot chat because each tool result is copied back into the prompt ([Chapter 1](./01-llms-at-a-practical-level.md)).

---

## 3. The loop in one line

```text
observe (read state) → think (model proposes text or tool calls) → act (run tools, append results) → observe → … → stop
```

**Stop** when:

- The model returns a **final** user-facing message (your policy defines how you detect that), or  
- **Max iterations** / **token budget** / **time** is exceeded, or  
- A **human** or **validator** rejects the trajectory  

Industrial systems add **retries**, **idempotent** tools, and **logging** of each step for debugging and evals.

---

## 4. Where this pattern comes from (references)

**ReAct (reasoning + acting).** Interleaves natural language “thought” with tool use; the paper formalizes the idea that an LLM can alternate reasoning traces and actions in an environment ([Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629)).

**Tool use in products (documentation).**

- OpenAI describes **function calling** / tools so the model can emit structured calls your backend runs ([OpenAI: function calling](https://platform.openai.com/docs/guides/function-calling)). Newer **Agents** and **Responses** APIs extend the same idea ([OpenAI: agents guide](https://platform.openai.com/docs/guides/agents)).  
- Anthropic documents **tool use** for Claude: defining tools, passing tool results back in the message list, and multi-step workflows ([Anthropic: tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)).  
- **Model Context Protocol (MCP)** standardizes how clients discover and invoke tools hosted by a server; the agent loop still lives in the **client** ([MCP specification](https://modelcontextprotocol.io/specification/2025-11-25), [MCP introduction](https://modelcontextprotocol.io/introduction)).

**Takeaway.** “Agent” in production is usually: **your loop** + **vendor tool-calling format** + **MCP or custom adapters** for concrete systems.

---

## 5. Example A — Chatbot: one call, no tools

The user asks for a product of two numbers. A minimal “chatbot” pipes the question to the model once and returns the string. There is no calculator—if the model mis-multiplies, that wrong number is what the user sees.

```python
def chatbot_answer(user_text: str, call_llm) -> str:
    """Single model call; no tools; no second chance."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_text},
    ]
    return call_llm(messages).strip()
```

Here `call_llm` is any wrapper around an API from [Chapter 2](./02-api-usage-three-providers.md).

---

## 6. Example B — Agent: same task with a tool and a loop

We give the model access to a real `multiply` function. The **orchestrator** keeps calling the model until it either uses the tool and then answers, or answers directly. For teaching, the “model” below is **stubbed** so you can run the file without API keys; in production you replace `model_step` with a real tool-capable completion.

**Tools registry** (the `act` phase only calls these):

```python
def multiply(a: int, b: int) -> int:
    return a * b

TOOLS = {"multiply": multiply}
```

**Stub model** (simulates two-step ReAct-style behavior: first tool call, then final answer after seeing the tool result):

```python
def model_step(messages: list[dict]) -> dict:
    """
    Returns either:
      {"kind": "final", "text": str}
      {"kind": "tool", "name": str, "arguments": dict}
    """
    last_user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    tool_results = [m for m in messages if m["role"] == "tool"]

    if not tool_results and "24" in last_user and "17" in last_user:
        return {"kind": "tool", "name": "multiply", "arguments": {"a": 24, "b": 17}}

    if tool_results:
        return {"kind": "final", "text": "24 * 17 = 408 (computed with the multiply tool)."}

    return {"kind": "final", "text": "I am not sure how to help without a tool."}
```

**Agent loop** (observe → think → act → observe → stop):

```python
def run_agent(user_text: str, max_steps: int = 8) -> str:
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You may call tools to help the user. "
                "When you have the result, reply with a short final message."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        step = model_step(messages)  # think

        if step["kind"] == "final":
            return step["text"]  # stop

        name = step["name"]
        arguments = step["arguments"]
        if name not in TOOLS:
            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": f"error: unknown tool {name!r}",
                }
            )
            continue

        result = TOOLS[name](**arguments)  # act
        messages.append(
            {
                "role": "tool",
                "name": name,
                "content": str(result),
            }
        )
        # next iteration: observe expanded state

    return "Stopped: max_steps exceeded."
```

**Demo:**

```python
if __name__ == "__main__":
    q = "What is 24 * 17? Use the multiply tool if available."
    print(run_agent(q))
    # 24 * 17 = 408 (computed with the multiply tool).
```

**What to notice.**

- The **chatbot** path has no place for `multiply`; reliability depends on arithmetic in the weights.  
- The **agent** path moves arithmetic into **code**; the model’s job is to **choose** the tool and **interpret** the observation. That is the same division of labor described in OpenAI and Anthropic tool-use docs ([OpenAI function calling](https://platform.openai.com/docs/guides/function-calling), [Anthropic tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)).

---

## 7. Mapping the stub to real APIs

Real providers return **assistant** messages that may include **tool call** payloads (names and JSON arguments), not your custom `model_step` dict. Your loop still:

1. Appends the assistant message from the API.  
2. Runs each tool.  
3. Appends **tool** / **tool_result** messages exactly as the vendor’s schema requires.  
4. Calls the API again until the model stops requesting tools.  

Details differ between OpenAI, Anthropic, and Google; the **shape** of the loop is the same.

---

## 8. Suggested reading order

1. [Yao et al. — ReAct](https://arxiv.org/abs/2210.03629) (paper; optional skim of the algorithm diagrams)  
2. [OpenAI — Function calling](https://platform.openai.com/docs/guides/function-calling) and [Agents](https://platform.openai.com/docs/guides/agents)  
3. [Anthropic — Tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)  
4. [Model Context Protocol — Introduction](https://modelcontextprotocol.io/introduction)  

---

[← Chapter 2](./02-api-usage-three-providers.md) · [Book home](./README.md) · [Chapter 4 →](./04-city-coordinates-cache-open-meteo.md)
