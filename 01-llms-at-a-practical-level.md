# Chapter 1 — LLMs at a practical level

This chapter corresponds to **Step 1** under *Phase 1 — Learn the minimum foundations* in [this book’s README](./README.md). Use the linked vendor documentation when you need authoritative definitions.

*Tax and estate figures in this chapter are simplified teaching examples only; real law is more complex and changes over time.*

By the end of this chapter you should be comfortable with: **tokens and context windows**; **temperature and sampling**; **prompting**; **structured JSON**; **why models hallucinate**; and **why fluent reasoning is not the same as truth**.

**Deliverable.** Build a few simple prompts that reliably return **structured JSON**, and understand where validation and retries belong in real systems.

---

## Tokens and context windows

APIs do not bill or bound memory in “characters.” They use **tokens**: pieces of text produced by a **tokenizer**, which may be whole words, subwords, or punctuation ([OpenAI tokenizer](https://platform.openai.com/tokenizer), [OpenAI: what are tokens](https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them)).

The **context window** is the maximum number of tokens the model can attend to in one request. How input and output share that budget depends on the API and model. Long system prompts, long chat history, retrieved documents, and long tool outputs all draw from the same limit ([OpenAI: models](https://platform.openai.com/docs/models), [Anthropic: context windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows)).

**Why this matters for agents.** Loops append tool results and prior turns; you exhaust context faster than in a single question-and-answer turn. Cost and latency usually scale with tokens ([OpenAI pricing](https://openai.com/api/pricing/)).

---

## Temperature and sampling

**Temperature** scales how “sharp” the next-token distribution is before sampling. Lower values favor high-probability tokens; higher values spread probability mass and increase variety—sometimes at the cost of coherence ([OpenAI Chat Completions: `temperature`](https://platform.openai.com/docs/api-reference/chat/create)). **Top-p** (nucleus sampling) restricts sampling to a set of tokens whose cumulative probability reaches a threshold *p*; it adapts to the shape of the distribution and is often documented next to temperature on the same API page ([OpenAI Chat Completions: `top_p`](https://platform.openai.com/docs/api-reference/chat/create)).

For **reproducible** tests or evaluations, hold sampling settings fixed (for example `temperature` near zero where appropriate). On OpenAI’s API, the **`seed`** parameter, together with identical request parameters, improves repeatability; backend changes can still alter outputs slightly ([OpenAI: advanced usage](https://platform.openai.com/docs/guides/advanced-usage)).

### How sampling works at a glance

At each step the model produces a distribution over vocabulary items; **sampling** is the rule for **choosing** the next token from that distribution.

**Greedy decoding** always picks the highest-probability token. It is stable but can be repetitive; it behaves like very low temperature.

**Random sampling** draws stochastically according to probabilities. Temperature reshapes the distribution before this draw: low temperature makes the distribution peaky (closer to greedy); high temperature flattens it (more exploration).

**Top-k sampling** restricts the draw to the *k* highest-probability tokens, which caps the candidate set.

**Top-p (nucleus) sampling** keeps the smallest set of tokens whose total probability is at least *p*, then samples within that set. It tends to adapt better than a fixed *k* when the distribution is flat or spiky.

In practice the pipeline is: logits → temperature scaling → (optional) top-k or top-p filtering → sample one token.

### Practical defaults

- **Code, extraction, tool arguments:** lower temperature and tight schemas; always **validate** outputs.
- **Brainstorming or drafting:** somewhat higher temperature may help exploration.
- **Evaluations:** fix randomness as much as the platform allows so scores are comparable across runs.

---

## Prompting basics

When the API supports **roles**, separate **system** (stable rules), **user** (the task), and **assistant** (prior model turns). That structure usually beats one undifferentiated block of text ([OpenAI: prompt engineering](https://platform.openai.com/docs/guides/prompt-engineering), [Anthropic: prompt engineering overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)).

State the **output shape** explicitly (for example “return only JSON” and field names) and the **failure behavior** (for example “if unknown, use `null`”). A few **concrete examples** in the prompt often outperform long prose about formatting ([OpenAI: prompt engineering tactics](https://platform.openai.com/docs/guides/prompt-engineering)).

### Example: extracting tax-related fields

Suppose the input is:

```text
The estate tax rate is 40% and applies to assets above $13 million.
```

A production-style prompt might combine roles, schema, rules, and a **few-shot** example:

**System:** You are an information extraction engine. Return ONLY valid JSON. No prose outside the JSON.

**User:** Extract tax policy information from the input.

Schema (illustrative types, not strict JSON Schema):

```json
{
  "tax_type": "string",
  "rate": "number | null",
  "threshold": "number | null",
  "currency": "string | null"
}
```

Here `threshold` means the dollar level the text implies for where a rate applies (in the estate example below, it aligns with an **exemption** amount in the later “estate tax owed” section—same dollar idea, different field name in extraction vs. policy APIs).

Rules:

- Express `rate` as a decimal (for example `0.4` for 40%).
- Express `threshold` as a number without commas.
- Use `null` for any field you cannot infer.

Example:

- Input: `"The income tax rate is 25% for income above $50,000."`
- Output:

```json
{
  "tax_type": "income tax",
  "rate": 0.25,
  "threshold": 50000,
  "currency": "USD"
}
```

Now process:

```text
The estate tax rate is 40% and applies to assets above $13 million.
```

A stable target output:

```json
{
  "tax_type": "estate tax",
  "rate": 0.4,
  "threshold": 13000000,
  "currency": "USD"
}
```

**Engineering view.** You are effectively defining a **function contract**: types, constraints, and tests (the example). Additional lines such as “Do not include explanations” and “Output must parse with `json.loads` in Python” are appropriate when this block feeds an ETL or downstream service.

---

## Structured output and JSON

For experiments you can ask for JSON in plain language. For production, prefer API features that **constrain** structure—JSON mode, structured outputs against a schema, or tool and function definitions—and always **parse and validate** on your side with a real JSON parser and schema validator ([OpenAI: structured outputs](https://platform.openai.com/docs/guides/structured-outputs), [OpenAI: JSON mode](https://platform.openai.com/docs/guides/text-generation/json-mode)).

Treat the raw model string as **untrusted**: it can be malformed JSON under load or adversarial prompts. Your code should parse, validate, retry or repair, and fall back safely.

Tool calls in agents are also **structured** (name and arguments). The same discipline applies: schema, validation, retries.

### Example: extraction pipeline with validation and retries

Define a strict schema (here with Pydantic):

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

class TaxInfo(BaseModel):
    tax_type: str
    rate: Optional[float] = Field(None, ge=0, le=1)
    threshold: Optional[float] = None
    currency: Optional[str] = None
```

Prompt template (soft constraints plus few-shot):

```python
PROMPT = """
You are an information extraction engine.
Return ONLY valid JSON.

Schema:
{{
  "tax_type": string,
  "rate": number | null,
  "threshold": number | null,
  "currency": string | null
}}

Rules:
- rate must be decimal (0.4 for 40%)
- threshold must be numeric (no commas)
- if unknown, use null
- no extra text

Example:
Input: "The income tax rate is 25% for income above $50,000."
Output:
{{
  "tax_type": "income tax",
  "rate": 0.25,
  "threshold": 50000,
  "currency": "USD"
}}

Now process:
{input}
"""
```

Core loop:

```python
import json

def extract_tax_info(llm_call, text: str, max_retries=3) -> TaxInfo:
    # Braces in the JSON above are doubled ({{ }}) so str.format only substitutes {input}.
    prompt = PROMPT.format(input=text)

    for attempt in range(max_retries):
        raw_output = llm_call(prompt)

        try:
            data = json.loads(raw_output)
            validated = TaxInfo(**data)
            return validated

        except (json.JSONDecodeError, ValidationError) as e:
            print(f"[Retry {attempt+1}] Failed: {e}")
            # Avoid f-strings if raw_output might contain "{" / "}"; build the string explicitly.
            prompt = (
                "Fix the JSON below to match the schema. Return ONLY valid JSON.\n\n"
                "Schema:\n"
                + str(TaxInfo.model_json_schema())
                + "\n\nInvalid JSON:\n"
                + raw_output
            )

    return TaxInfo(
        tax_type="unknown",
        rate=None,
        threshold=None,
        currency=None,
    )
```

A stub caller might return valid JSON for testing:

```python
def llm_call(prompt: str) -> str:
    # Replace with OpenAI, Anthropic, or another API.
    return """
    {
      "tax_type": "estate tax",
      "rate": 0.4,
      "threshold": 13000000,
      "currency": "USD"
    }
    """
```

**What this illustrates.**

1. **JSON from the model is not trusted** until `json.loads` succeeds.
2. **Schema validation** catches wrong types, missing fields, and illegal values (for example `rate` outside `[0, 1]`).
3. **Retry with a repair prompt** is a common production pattern.
4. **Fallback** values prevent the whole pipeline from crashing when all retries fail.
5. **Prompt templates:** if you embed example JSON inside a `str.format` template, literal braces must be doubled (`{{` / `}}`); only the placeholder (here `{input}`) stays single-braced.
6. The design is **probabilistic model → deterministic boundary**: the LLM may err; parsing, validation, and fallback contain that uncertainty.

**Runnable companion (OpenAI + `.env`).** [`code/ch01_tax_extraction.py`](./code/ch01_tax_extraction.py) runs this pipeline end to end. Install and keys: [`code/README.md`](./code/README.md).

---

## Why models hallucinate

**Hallucination** here means outputs that are **wrong or unsupported** by the context or the facts, sometimes stated with high confidence. Vendors document limitations and mitigation at a high level ([OpenAI: model limitations](https://help.openai.com/en/articles/7864572-what-is-an-ai-model-limitation), [Anthropic: minimizing hallucinations](https://docs.anthropic.com/en/docs/minimizing-hallucinations), [Anthropic Help: misleading responses](https://support.anthropic.com/en/articles/8525154-claude-is-providing-incorrect-or-misleading-responses-what-s-going-on)).

In **policy, tax, or modeling** work, the failure mode is often not a crash but **silent contamination**: a wrong rate skews every downstream number; a fabricated threshold breaks a simulation; a citation to a nonexistent rule undermines trust.

Mitigations you will reuse in agents:

**Retrieval and citations.** Do not ask the model to invent facts from memory. Retrieve passages or rows from databases and documents, inject them as context, and ask the model to **ground** answers in that material—or to abstain when evidence is missing.

**Tools.** Let the model **call** functions that return authoritative values (for example the same idea as `get_estate_tax_policy(year)` in the section below). The LLM orchestrates; numbers come from systems you control and can audit.

**Human review.** For finance, tax, law, medicine, or any domain where errors are costly, treat model output as a **draft** until a human approves—or restrict automation to low-risk steps.

**Evaluations.** Judge outputs against **ground truth** or checks, not vibes: unit-style tests on extracted fields, comparison to databases, regression suites when prompts or models change.

**Agents without these guards** may invent tool parameters, intermediate results, or final answers. **With** retrieval, tools, validation, and evals, the pattern becomes: LLM for **decisions** and language; tools and data stores for **facts**; validators for **what may enter the system**.

---

## Why “reasoning” is not the same as “truth”

Extended **chain-of-thought-style** text is **not** a proof of correctness. It can expose useful steps or it can rationalize mistakes. Treat it as **audit material**, not verification ([Wei et al., chain-of-thought prompting](https://arxiv.org/abs/2201.11903); [Bender et al., stochastic parrots](https://dl.acm.org/doi/10.1145/3442188.3445922)). For agents, **verify** critical claims with tools, databases, or primary sources when stakes are high.

### Example: estate tax owed

**Question:** What is the estate tax owed on $15M in 2024?

**Assumed ground truth for the exercise:** exemption $13M; rate 40% on the amount above the exemption only (so taxable estate above the exemption is `(15M − 13M) × 0.4 = $800,000`).

A **tool** returns policy from your system of record:

```python
def get_estate_tax_policy(year: int):
    return {
        "rate": 0.4,
        "exemption": 13_000_000,
        "applies_to": "amount_above_threshold",
    }
```

The model might propose a **plan** (fetch policy, compute taxable base, apply rate). The plan can be imperfect in wording; what matters for correctness is that **policy and arithmetic** come from defined code and data:

```python
policy = get_estate_tax_policy(2024)
taxable = max(0, 15_000_000 - policy["exemption"])
tax = taxable * policy["rate"]
```

You shift reliance from “the model reasoned correctly” to “the **data** and **computation** are correct.” Add **sanity checks** in code when appropriate (for example non-negative tax, tax not exceeding a trivial upper bound, or equality against a closed-form expected value in tests).

**Agent posture in one line:** the LLM may **decide**; tools and code must supply **facts** and **deterministic math**; validators and evals enforce **trust boundaries**.

---

## Suggested reading order

1. [OpenAI — Prompt engineering](https://platform.openai.com/docs/guides/prompt-engineering)  
2. [OpenAI — Structured outputs](https://platform.openai.com/docs/guides/structured-outputs) (or JSON mode where applicable)  
3. [Anthropic — Prompt engineering overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)  
4. [OpenAI — Model limitations](https://help.openai.com/en/articles/7864572-what-is-an-ai-model-limitation)  

---

[Book home](./README.md) · [Chapter 2 — API usage →](./02-api-usage-three-providers.md)
