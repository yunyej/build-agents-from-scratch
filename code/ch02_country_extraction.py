"""
Chapter 2 — OpenAI Chat Completions: one call, structured JSON, Pydantic validation.

Run: python ch02_country_extraction.py
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from common import OPENAI_KEY_HINT, load_env


class CountryInfo(BaseModel):
    country: str = Field(min_length=1)
    capital: str = Field(min_length=1)
    population_millions: float = Field(gt=0)


USER_BODY = """
Extract structured data from the text below. Use these rules:
- country: common English name
- capital: city name
- population_millions: number (e.g. 68 for 68 million)

Text:
France is in Western Europe. Its capital is Paris. Population is about 68 million.
"""


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
                "content": USER_BODY
                + '\nRespond with JSON keys: "country", "capital", "population_millions".',
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


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    info = extract_with_openai()
    print(info.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
