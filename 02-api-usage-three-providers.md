# Chapter 2 — API usage (OpenAI, Anthropic, Google)

This chapter corresponds to **Step 2** under *Phase 1 — Learn the minimum foundations* in [this book’s README](./README.md). It assumes you have read [Chapter 1 — LLMs at a practical level](./01-llms-at-a-practical-level.md).

The patterns are the same across vendors: **authenticate → build messages → call → extract text → parse → validate**.

By the end of this chapter you should be able to: **send** system and user messages through an official client; **read** the response text (or structured payload); **parse** JSON safely; and **handle** common failures (HTTP errors, rate limits, malformed output).

**Deliverable.** A small script (or three tiny functions) that asks a model for **structured JSON**, validates it, and degrades gracefully when parsing fails.

The three providers below are the most common commercial APIs in tutorials and products today: **OpenAI** (GPT family), **Anthropic** (Claude), and **Google** (Gemini).

---

## 1. What is common across providers

| Idea | Role |
|------|------|
| **API key** | Secret you pass via environment variable or client config. Never commit it to git ([OpenAI: API keys](https://platform.openai.com/docs/api-reference/authentication), [Anthropic: API keys](https://docs.anthropic.com/en/api/overview), [Google: Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)). |
| **Model id** | String such as `gpt-4o-mini` or `claude-sonnet-4-20250514`. Models change; check each vendor’s **model list** when something 404s or deprecates ([OpenAI models](https://platform.openai.com/docs/models), [Anthropic models](https://docs.anthropic.com/en/docs/about-claude/models/overview), [Gemini models](https://ai.google.dev/gemini-api/docs/models/gemini)). |
| **Messages** | Usually a **system** instruction (stable rules) plus **user** content (the task). Some APIs put “system” in a separate parameter instead of inside the message list. |
| **Sampling** | Parameters like `temperature` appear on all three; defaults differ. See Chapter 1. |
| **Structured output** | Prefer vendor features that **constrain** JSON (OpenAI `response_format`, Gemini `response_mime_type` + schema, Anthropic prompt + optional betas/tools per their docs). Still **validate** with Pydantic or JSON Schema on your side. |

Environment variables used in this chapter:

- `OPENAI_API_KEY` — OpenAI  
- `ANTHROPIC_API_KEY` — Anthropic  
- `GEMINI_API_KEY` — Google Gemini (recommended name in current [Gemini quickstart](https://ai.google.dev/gemini-api/docs/quickstart))

---

## 2. Shared task and schema (all three examples)

We use one extraction task so you can compare APIs side by side.

**Input text (embedded in the prompt):**

```text
France is in Western Europe. Its capital is Paris. Population is about 68 million.
```

**Target JSON shape:**

```json
{
  "country": "France",
  "capital": "Paris",
  "population_millions": 68
}
```

**Pydantic model (Python validation after the call):**

```python
from pydantic import BaseModel, Field

class CountryInfo(BaseModel):
    country: str = Field(min_length=1)
    capital: str = Field(min_length=1)
    population_millions: float = Field(gt=0)
```

**Shared prompt body** (prepend instructions per provider if needed):

```python
USER_BODY = """
Extract structured data from the text below. Use these rules:
- country: common English name
- capital: city name
- population_millions: number (e.g. 68 for 68 million)

Text:
France is in Western Europe. Its capital is Paris. Population is about 68 million.
"""
```

---

## 3. OpenAI (GPT) — Chat Completions

Official Python SDK: [`openai`](https://github.com/openai/openai-python). Reference: [Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create), [OpenAI Python library](https://platform.openai.com/docs/libraries/python).

**Install:** `pip install openai`

**Pattern:** `client.chat.completions.create` with `messages` and, for JSON-only answers, `response_format={"type": "json_object"}`. You must still ask for JSON in the prompt when using `json_object` mode ([JSON mode](https://platform.openai.com/docs/guides/text-generation/json-mode)).

```python
import json
import os
from openai import OpenAI
from pydantic import ValidationError

def extract_with_openai() -> CountryInfo:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You return only one JSON object, no markdown, no explanation.",
            },
            {
                "role": "user",
                "content": USER_BODY + '\nRespond with JSON keys: "country", "capital", "population_millions".',
            },
        ],
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise ValueError("Empty content from OpenAI")
    try:
        return CountryInfo.model_validate_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Schema mismatch: {e}") from e
```

**Extracting text:** `completion.choices[0].message.content` ([response shape](https://platform.openai.com/docs/api-reference/chat/object)).

**Failures to catch:** network errors from the SDK, `RateLimitError`, empty `content`, `JSONDecodeError`, `ValidationError`. The SDK maps HTTP errors to typed exceptions ([OpenAI errors guide](https://platform.openai.com/docs/guides/error-codes)).

**Runnable companion (OpenAI only).** [`code/ch02_country_extraction.py`](./code/ch02_country_extraction.py) matches this section’s pattern. Setup: [`code/README.md`](./code/README.md).

---

## 4. Anthropic (Claude) — Messages API

Official Python SDK: [`anthropic`](https://github.com/anthropics/anthropic-sdk-python). Reference: [Messages API](https://docs.anthropic.com/en/api/messages), [Anthropic Python SDK](https://docs.anthropic.com/en/api/client-sdks).

**Install:** `pip install anthropic`

**Pattern:** `client.messages.create` with `model`, `max_tokens`, optional `system`, and `messages=[{"role": "user", "content": ...}]`. The response is a list of **content blocks**; plain text is in a block with `type == "text"` ([message response format](https://docs.anthropic.com/en/api/messages)).

Anthropic’s **structured outputs** and tool-use features evolve; for a minimal Step-2 script, strict prompting plus `model_validate_json` is enough. See [Structured outputs](https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs) when you want schema enforcement on the API side.

```python
import json
import os
import anthropic
from pydantic import ValidationError

def anthropic_text_content(message) -> str:
    for block in message.content:
        if block.type == "text":
            return block.text
    raise ValueError("No text block in Anthropic response")

def extract_with_anthropic() -> CountryInfo:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0,
        system="You return only one JSON object, no markdown fences, no explanation.",
        messages=[
            {
                "role": "user",
                "content": USER_BODY
                + '\nRespond with JSON keys: "country", "capital", "population_millions".',
            },
        ],
    )
    raw = anthropic_text_content(message)
    try:
        return CountryInfo.model_validate_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Schema mismatch: {e}") from e
```

**Model string:** replace with a current Claude model id from [Anthropic’s model overview](https://docs.anthropic.com/en/docs/about-claude/models/overview) if this id is unavailable in your account.

---

## 5. Google (Gemini) — Google GenAI SDK

Official Python package: [`google-genai`](https://pypi.org/project/google-genai/). Reference: [Gemini API quickstart](https://ai.google.dev/gemini-api/docs/quickstart), [Structured output (JSON Schema)](https://ai.google.dev/gemini-api/docs/structured-output), [Python libraries](https://ai.google.dev/gemini-api/docs/libraries).

**Install:** `pip install google-genai`

**Pattern:** `from google import genai` then `genai.Client()` (reads `GEMINI_API_KEY` by default). Use `generate_content` with `config` containing `response_mime_type` and `response_json_schema` so the model is steered into valid JSON for your Pydantic model ([structured output example](https://ai.google.dev/gemini-api/docs/structured-output)).

```python
import json
import os
from google import genai
from pydantic import ValidationError

def extract_with_gemini() -> CountryInfo:
    # Uses GEMINI_API_KEY; see https://ai.google.dev/gemini-api/docs/api-key
    _ = os.environ["GEMINI_API_KEY"]
    client = genai.Client()
    schema = CountryInfo.model_json_schema()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=USER_BODY,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": schema,
        },
    )
    raw = response.text
    if not raw:
        raise ValueError("Empty content from Gemini")
    try:
        return CountryInfo.model_validate_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Schema mismatch: {e}") from e
```

**Model string:** use a current Gemini model from [the models doc](https://ai.google.dev/gemini-api/docs/models/gemini); names change over time.

---

## 6. One file that tries all three (optional)

You can wire the functions behind a small CLI or `if __name__ == "__main__"` block. Only call the provider whose key is set.

```python
if __name__ == "__main__":
    import sys

    if os.getenv("OPENAI_API_KEY"):
        print(extract_with_openai())
    elif os.getenv("ANTHROPIC_API_KEY"):
        print(extract_with_anthropic())
    elif os.getenv("GEMINI_API_KEY"):
        print(extract_with_gemini())
    else:
        print("Set one of OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY", file=sys.stderr)
        sys.exit(1)
```

---

## 7. Failure handling checklist

| Failure | What to do |
|---------|------------|
| **Missing / wrong API key** | Fail fast with a clear message; never log the full key. |
| **Rate limit (429)** | Exponential backoff and retry with a cap; respect `Retry-After` when present ([OpenAI rate limits](https://platform.openai.com/docs/guides/rate-limits)). |
| **Timeout / network** | Retry idempotent reads; surface last error after N attempts. |
| **Empty model text** | Treat as error; log request id if the platform returns one. |
| **Invalid JSON** | Retry once with a “fix this JSON” prompt (see Chapter 1) or fall back to a safe default. |
| **Schema validation** | Same as Chapter 1: `ValidationError` means the model drifted; do not pass bad data downstream. |

---

## 8. Suggested reading order

1. [OpenAI — Chat Completions](https://platform.openai.com/docs/api-reference/chat/create) and [Python library](https://platform.openai.com/docs/libraries/python)  
2. [Anthropic — Messages API](https://docs.anthropic.com/en/api/messages) and [Python SDK](https://docs.anthropic.com/en/api/client-sdks)  
3. [Google — Gemini quickstart](https://ai.google.dev/gemini-api/docs/quickstart) and [structured output](https://ai.google.dev/gemini-api/docs/structured-output)  
4. [OpenAI — Error codes](https://platform.openai.com/docs/guides/error-codes)  

---

[← Chapter 1](./01-llms-at-a-practical-level.md) · [Book home](./README.md) · [Chapter 3 →](./03-chatbot-vs-agent-and-the-loop.md)
