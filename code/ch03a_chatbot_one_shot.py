"""
Chapter 3 — Chatbot pattern: a single model call, no tools.

The model must do arithmetic in weights; there is no multiply function.
Run: python ch03a_chatbot_one_shot.py
"""

from __future__ import annotations

import os
import sys

from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env


def chatbot_answer(user_text: str) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": user_text},
        ],
    )
    raw = completion.choices[0].message.content
    return (raw or "").strip()


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    q = "What is 24 * 17? Reply with one short sentence including the numeric result."
    print(chatbot_answer(q))


if __name__ == "__main__":
    main()
