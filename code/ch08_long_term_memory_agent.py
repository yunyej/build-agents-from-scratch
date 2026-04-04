from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"

CHAT_MODEL = "gpt-4o-mini"

_REMEMBER_RE = re.compile(r"^\s*remember:\s*(.+)\s*$", re.I)
_FORGET_RE = re.compile(r"^\s*forget:\s*(.+)\s*$", re.I)


@dataclass
class UserProfile:
    """
    Deliberately small allowlist.
    Keep memory structured so you can inspect and delete it.
    """

    preferences: dict[str, Any] = field(default_factory=dict)
    recurring_facts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "preferences": self.preferences,
                "recurring_facts": self.recurring_facts,
                "notes": self.notes,
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "UserProfile":
        p = UserProfile()
        p.preferences = dict(d.get("preferences") or {})
        p.recurring_facts = dict(d.get("recurring_facts") or {})
        p.notes = list(d.get("notes") or [])
        return p


ALLOWED_PREF_KEYS = {"style", "risk_posture", "citation_preference"}
ALLOWED_FACT_KEYS = {"marital_status", "num_children", "income_range_usd"}


def profile_path(user_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", user_id.strip())
    return PROFILE_DIR / f"{safe}.json"


def load_profile(user_id: str) -> UserProfile:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    p = profile_path(user_id)
    if not p.exists():
        return UserProfile()
    return UserProfile.from_dict(json.loads(p.read_text(encoding="utf-8")))


def save_profile(user_id: str, profile: UserProfile) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    # Atomic write: prevents corrupt JSON on crash/interruption.
    # Write to a temp file in the same directory, then replace.
    final_path = profile_path(user_id)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    tmp_path.write_text(profile.to_json() + "\n", encoding="utf-8")
    tmp_path.replace(final_path)


def apply_remember(profile: UserProfile, text: str) -> str:
    """
    Extremely small rule-based parser so the demo is deterministic.
    Real systems usually do: model -> JSON schema -> human approve -> persist.
    """
    t = text.strip()
    lower = t.lower()

    # Preferences
    if "prefer short" in lower or "keep it short" in lower:
        profile.preferences["style"] = "short"
        return "Saved preference: style=short"
    if "prefer detailed" in lower or "be detailed" in lower:
        profile.preferences["style"] = "detailed"
        return "Saved preference: style=detailed"
    if "conservative" in lower:
        profile.preferences["risk_posture"] = "conservative"
        return "Saved preference: risk_posture=conservative"

    # Facts
    m = re.search(r"\b(\d+)\s*(kids|children|dependents)\b", lower)
    if m:
        profile.recurring_facts["num_children"] = int(m.group(1))
        return f"Saved fact: num_children={m.group(1)}"
    if "married" in lower:
        profile.recurring_facts["marital_status"] = "married"
        return "Saved fact: marital_status=married"

    # Fallback note (user approved by using remember:)
    profile.notes.append(t[:240])
    profile.notes = profile.notes[-20:]
    return "Saved note."


def apply_forget(profile: UserProfile, key: str) -> str:
    k = key.strip()
    if not k:
        return "Nothing to forget."

    # Allow forgetting by exact key or by category.key
    if "." in k:
        cat, sub = k.split(".", 1)
        cat = cat.strip()
        sub = sub.strip()
        if cat == "preferences" and sub in profile.preferences:
            del profile.preferences[sub]
            return f"Forgot preferences.{sub}"
        if cat == "recurring_facts" and sub in profile.recurring_facts:
            del profile.recurring_facts[sub]
            return f"Forgot recurring_facts.{sub}"
        return "No such stored field."

    # Try keys in both dicts
    if k in profile.preferences:
        del profile.preferences[k]
        return f"Forgot preferences.{k}"
    if k in profile.recurring_facts:
        del profile.recurring_facts[k]
        return f"Forgot recurring_facts.{k}"
    return "No such stored field."


def profile_injection(profile: UserProfile) -> str:
    prefs = {k: v for k, v in profile.preferences.items() if k in ALLOWED_PREF_KEYS}
    facts = {k: v for k, v in profile.recurring_facts.items() if k in ALLOWED_FACT_KEYS}
    notes = profile.notes[-5:]
    return (
        "[USER_PROFILE]\n"
        f"preferences: {json.dumps(prefs, ensure_ascii=False)}\n"
        f"recurring_facts: {json.dumps(facts, ensure_ascii=False)}\n"
        f"notes: {json.dumps(notes, ensure_ascii=False)}\n"
    )


def answer_with_profile(client: OpenAI, profile: UserProfile, user_text: str) -> str:
    system = (
        "You are a helpful assistant. Use the [USER_PROFILE] to avoid repeating questions and to match user preferences. "
        "If the profile doesn't contain needed facts, ask a brief clarifying question. "
        "Do not claim you remember things that are not in the profile."
    )
    user = f"{profile_injection(profile)}\n\nUser message:\n{user_text}"
    r = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (r.choices[0].message.content or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="default", help="user id (profile key)")
    args = parser.parse_args()

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(OPENAI_KEY_HINT)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    profile = load_profile(args.user)

    print(f"Long-term memory agent (user={args.user!r}). Commands: remember: … | forget: <key> | empty line exits.")
    while True:
        try:
            user_text = input("\nYou> ").strip()
        except EOFError:
            break
        if not user_text:
            break

        m = _REMEMBER_RE.match(user_text)
        if m:
            msg = apply_remember(profile, m.group(1))
            save_profile(args.user, profile)
            print(f"\nAgent> {msg}")
            continue

        m = _FORGET_RE.match(user_text)
        if m:
            msg = apply_forget(profile, m.group(1))
            save_profile(args.user, profile)
            print(f"\nAgent> {msg}")
            continue

        assistant_text = answer_with_profile(client, profile, user_text)
        print(f"\nAgent> {assistant_text}")


if __name__ == "__main__":
    main()

