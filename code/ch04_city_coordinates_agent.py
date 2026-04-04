"""
Chapter 4 — One LLM tool: city latitude/longitude with SQLite cache + Open-Meteo online geocoding.

The model only sees get_city_coordinates(city_name). Inside Python:
  1) look up normalized city key in SQLite;
  2) if missing, call Open-Meteo geocoding HTTP API, then INSERT and return.

Run: python ch04_city_coordinates_agent.py
      python ch04_city_coordinates_agent.py "What are the coordinates of Tokyo?"
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from common import OPENAI_KEY_HINT, load_env

DB_PATH = Path(__file__).resolve().parent / "ch04_city_coords.sqlite"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _normalize_city_key(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS city_coords (
            query_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _lookup_cache(query_key: str) -> tuple[str, float, float] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT display_name, latitude, longitude FROM city_coords WHERE query_key = ?",
            (query_key,),
        ).fetchone()
    if row is None:
        return None
    return row[0], float(row[1]), float(row[2])


def _save_cache(query_key: str, display_name: str, lat: float, lon: float) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO city_coords (query_key, display_name, latitude, longitude)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(query_key) DO UPDATE SET
                display_name = excluded.display_name,
                latitude = excluded.latitude,
                longitude = excluded.longitude
            """,
            (query_key, display_name, lat, lon),
        )
        conn.commit()


def _geocode_online(city_name: str) -> tuple[str, float, float] | str:
    """Call Open-Meteo geocoding. Returns (display_name, lat, lon) or error string."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(GEO_URL, params={"name": city_name.strip(), "count": 1})
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            if not results:
                return f"error: no geocoding results for {city_name!r}"
            top = results[0]
            lat, lon = top.get("latitude"), top.get("longitude")
            if lat is None or lon is None:
                return "error: geocoding response missing coordinates"
            label = top.get("name", city_name.strip())
            admin = top.get("admin1") or top.get("country") or ""
            display = f"{label}" + (f", {admin}" if admin else "")
            return (display, float(lat), float(lon))
    except httpx.HTTPError as e:
        return f"error: geocoding request failed: {e}"


def get_city_coordinates(city_name: str) -> str:
    """
    Single tool exposed to the LLM: resolve latitude and longitude for a place name.
    Cache-first; on miss, uses Open-Meteo (online) and persists to SQLite.
    """
    raw = city_name.strip()
    if not raw:
        return "error: empty city name"

    key = _normalize_city_key(raw)
    cached = _lookup_cache(key)
    if cached is not None:
        display, lat, lon = cached
        return (
            f"{display}: latitude {lat}, longitude {lon}. "
            f"Source: local database cache (query_key={key!r})."
        )

    online = _geocode_online(raw)
    if isinstance(online, str):
        return online

    display, lat, lon = online
    _save_cache(key, display, lat, lon)
    return (
        f"{display}: latitude {lat}, longitude {lon}. "
        f"Source: Open-Meteo geocoding API (saved to local database for next time)."
    )


TOOLS_IMPL: dict[str, Any] = {"get_city_coordinates": get_city_coordinates}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_city_coordinates",
            "description": (
                "Look up latitude and longitude for a city or place name (e.g. Boston, Tokyo). "
                "Uses a local cache first, then a public geocoding service if needed. "
                "Call this whenever the user asks for coordinates, lat/long, or where a city is on the map."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "City or place name in plain text",
                    },
                },
                "required": ["city_name"],
            },
        },
    },
]


def assistant_to_message_dict(msg) -> dict[str, Any]:
    out: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content or "",
    }
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return out


def run_agent(user_text: str, max_steps: int = 8) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. "
                "When the user wants geographic coordinates (latitude and longitude) for a named place, "
                "call get_city_coordinates with the city or place name. "
                "For arithmetic, calculator-style questions, definitions, or any request that does not need "
                "geographic coordinates, answer directly and do not call tools."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=messages,
            tools=TOOLS_SPEC,
            tool_choice="auto",
        )
        msg = completion.choices[0].message
        messages.append(assistant_to_message_dict(msg))

        if not msg.tool_calls:
            return (msg.content or "").strip()

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name not in TOOLS_IMPL:
                out = f"error: unknown tool {name!r}"
            else:
                try:
                    out = str(TOOLS_IMPL[name](**args))
                except TypeError as e:
                    out = f"error: bad arguments for {name!r}: {e}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out,
                }
            )

    return "Stopped: max_steps exceeded."


def main() -> None:
    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        print(OPENAI_KEY_HINT, file=sys.stderr)
        sys.exit(1)

    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (
            "What are the latitude and longitude of Paris? "
            "Then ask again for the same city (Paris) so we can confirm cache behavior."
        )
    )
    print(run_agent(question))


if __name__ == "__main__":
    main()
