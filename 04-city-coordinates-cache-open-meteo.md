# Chapter 4 — City coordinates: cache + Open-Meteo

This chapter corresponds to **Step 4** under *Phase 2 — Build your first real agent* in [this book’s README](./README.md). It assumes [Chapter 3](./03-chatbot-vs-agent-and-the-loop.md) and [`code/ch03c_agent_openai_tools.py`](./code/ch03c_agent_openai_tools.py).

**Idea.** You expose **one** tool to the model—**`get_city_coordinates(city_name)`**—while your implementation uses a **local SQLite cache first**, then **Open-Meteo** geocoding on miss (still inside that single tool).

Your Python code implements a small pipeline:

1. **Normalize** the name (for example lowercase, trim spaces) and use it as a **lookup key**.  
2. **Query SQLite.** If a row exists, return latitude, longitude, and say the result came from the **local cache**.  
3. If there is **no row**, call **Open-Meteo’s geocoding HTTP API** (online “step 2”—*not* a second tool for the model), **insert** the result into SQLite, then return coordinates and say they were **fetched and saved**.

The model does not choose “database vs internet”; it only asks for coordinates. **You** choose cache vs network inside one tool. That keeps the tool surface small and matches the Step 4 goal of **one** clear capability.

**Deliverable.** An agent that answers ordinary questions in text, calls **`get_city_coordinates`** when the user wants lat/long for a place, and runs the usual **observe → model → tool? → append → model → stop** loop (ReAct-style via tool calling).

---

## 1. Why bundle cache + API inside one tool

- **Fewer failure modes for the model:** it cannot forget to check the cache or call the wrong order.  
- **Faster and cheaper on repeats:** second question about the same city avoids HTTP.  
- **Easier evals:** you can assert “second call hit cache” by logging or by inspecting the tool return string (`Source: local database cache` vs `saved to local database`).

If you later add **weather**, reuse the same resolution step in code (lookup coords → forecast) without giving the model two ways to geocode.

---

## 2. SQLite schema

Table **`city_coords`** (example):

| Column         | Purpose                                      |
|----------------|----------------------------------------------|
| `query_key`    | Primary key; normalized name for matching    |
| `display_name` | Human-readable label (e.g. `Paris, France`)|
| `latitude`     | Decimal degrees                              |
| `longitude`    | Decimal degrees                              |

Use **parameterized** SQL only (`?` placeholders). Never concatenate user input into SQL.

Reference: [Python sqlite3](https://docs.python.org/3/library/sqlite3.html).

---

## 3. Online geocoding (no API key): Open-Meteo

When the cache misses, call the public **geocoding** endpoint ([Open-Meteo geocoding API](https://open-meteo.com/en/docs/geocoding-api)):

- Example: `GET https://geocoding-api.open-meteo.com/v1/search?name=Paris&count=1`  
- Parse the first result’s `latitude`, `longitude`, and a display name from fields like `name`, `admin1`, `country`.  
- On success, **write** to SQLite and return a string that states coordinates **and** that they were fetched from the network.

Respect [Open-Meteo terms](https://open-meteo.com/en/terms); use timeouts (for example 10 seconds) and handle HTTP errors without crashing the agent loop.

---

## 4. OpenAI: one function in `tools`

Register a single function, `get_city_coordinates`, with one argument `city_name` ([function calling](https://platform.openai.com/docs/guides/function-calling)). The system prompt should say: use this tool when the user wants coordinates; otherwise answer directly.

The **agent loop** is the same as Chapter 3: call the model → if `tool_calls`, execute → append tool messages → repeat until a final assistant message.

**Whether to call the tool (Step 4).** With **`tool_choice="auto"`**, the model may return a normal assistant message with **no** `tool_calls` when tools are unnecessary. Calculator-style questions (`What is 15 + 27?`), chat, and non-geography tasks should be answered **in text only**—that *is* “the model decides whether to call the tool.” A clear **system prompt** (coordinates only → tool; math and general Q&A → no tool) keeps that behavior reliable. Your loop already branches correctly: **no tool calls → return `content`**.

---

## 5. Runnable script

See [`code/ch04_city_coordinates_agent.py`](./code/ch04_city_coordinates_agent.py). It creates **`ch04_city_coords.sqlite`** beside the script (gitignored via `code/ch04_*.sqlite` in the repo root `.gitignore`).

```bash
python ch04_city_coordinates_agent.py
python ch04_city_coordinates_agent.py "What are the coordinates of Boston?"
```

Try **Paris twice** in one prompt: the first resolution should mention **Open-Meteo** and **saved**; the second should mention **local database cache** (exact wording may vary slightly depending on the model’s paraphrase, but the tool output strings are stable).

---

## 6. Suggested reading order

1. [OpenAI — Function calling](https://platform.openai.com/docs/guides/function-calling)  
2. [Open-Meteo — Geocoding API](https://open-meteo.com/en/docs/geocoding-api)  
3. [Python — sqlite3](https://docs.python.org/3/library/sqlite3.html)  
4. [Chapter 3 — Chatbot vs agent](./03-chatbot-vs-agent-and-the-loop.md)  

---

[← Chapter 3](./03-chatbot-vs-agent-and-the-loop.md) · [Book home](./README.md) · [Chapter 5 →](./05-stop-conditions-and-safeguards.md) · [Runnable code](./code/ch04_city_coordinates_agent.py)
