"""Chapter 18 - Observability sketch: structured trace lines, retries, prompt version id.

Emits one JSON object per line on stderr for "events" (easy to ship to log aggregators later).

Run: python ch18_observability_demo.py list
     python ch18_observability_demo.py run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, TypeVar

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from common import OPENAI_KEY_HINT, load_env

T = TypeVar("T")

PROMPT_VERSION = "ch18-demo-1.0.0"
CHAT_MODEL = "gpt-4o-mini"


def trace_event(event: str, **fields: Any) -> None:
    line = json.dumps(
        {"event": event, "prompt_version": PROMPT_VERSION, **fields},
        ensure_ascii=False,
    )
    print(line, file=sys.stderr, flush=True)


def with_retries(
    label: str,
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.4,
) -> T:
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        trace_event("attempt", label=label, attempt=attempt)
        try:
            out = fn()
            trace_event("success", label=label, attempt=attempt)
            return out
        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            last = e
            trace_event("retryable_error", label=label, attempt=attempt, err=str(e))
            if attempt >= max_attempts:
                raise
            time.sleep(base_delay * attempt)
    raise last  # type: ignore[misc]


def one_completion(client: OpenAI) -> str:
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        max_tokens=80,
        messages=[
            {
                "role": "system",
                "content": f"You are a terse assistant. prompt_version={PROMPT_VERSION}",
            },
            {"role": "user", "content": "Reply in one sentence: what is observability?"},
        ],
    )
    return (r.choices[0].message.content or "").strip()


def cmd_list() -> None:
    print("Chapter 18 - Observability (patterns)\n")
    print("- trace_event: JSON lines on stderr (event, prompt_version, fields).")
    print("- with_retries: transient OpenAI errors (demo; real stack uses backoff+jitter).")
    print(f"- PROMPT_VERSION = {PROMPT_VERSION!r} (tie logs to prompt releases).")
    print("\nrun: logs trace lines to stderr, answer to stdout.")


def cmd_run() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0)
    trace_event("run_start", model=CHAT_MODEL)
    text = with_retries("chat", lambda: one_completion(client))
    trace_event("run_done", answer_chars=len(text))
    print(text)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", nargs="?", choices=["list", "run"], default="list")
    args = p.parse_args()
    if args.cmd == "list":
        cmd_list()
        return
    cmd_run()


if __name__ == "__main__":
    main()
