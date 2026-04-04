"""
Chapter 1 — Structured JSON extraction with validation and retries.

Uses OpenAI JSON mode + the TaxInfo schema from the chapter.
Run: python ch01_tax_extraction.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from common import OPENAI_KEY_HINT, load_env


class TaxInfo(BaseModel):
    tax_type: str
    rate: Optional[float] = Field(None, ge=0, le=1)
    threshold: Optional[float] = None
    currency: Optional[str] = None


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


def openai_json_completion(prompt: str) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You return only one JSON object. No markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise ValueError("Empty response from OpenAI")
    return raw.strip()


def extract_tax_info(text: str, max_retries: int = 3) -> TaxInfo:
    prompt = PROMPT.format(input=text)

    for attempt in range(max_retries):
        raw_output = openai_json_completion(prompt)

        try:
            data = json.loads(raw_output)
            return TaxInfo.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"[Retry {attempt + 1}] Failed: {e}", file=sys.stderr)
            prompt = (
                "Fix the JSON below to match the schema. Return ONLY valid JSON.\n\n"
                "Schema:\n"
                + json.dumps(TaxInfo.model_json_schema(), indent=2)
                + "\n\nInvalid JSON:\n"
                + raw_output
            )

    return TaxInfo(
        tax_type="unknown",
        rate=None,
        threshold=None,
        currency=None,
    )


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    sample = (
        "The estate tax rate is 40% and applies to assets above $13 million."
    )
    result = extract_tax_info(sample)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
