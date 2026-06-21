"""Live-fact grounding — the engine's "eyes" (third memory).

Binds the eternal example to present fact. Uses Tavily web search if
``TAVILY_API_KEY`` is set, via stdlib ``urllib`` only (no dependency, so it still
deploys to Render with nothing to install). Returns a short text block the engine
folds into the answer, or "" when no key / on any error (the engine then opens an
Evidence gap instead of faking facts).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

TAVILY_URL = "https://api.tavily.com/search"


def tavily_search(query: str, api_key: str | None = None,
                  max_results: int = 4, timeout: int = 15) -> str:
    api_key = api_key or os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return ""
    payload = json.dumps({
        "api_key": api_key, "query": query,
        "max_results": max_results, "search_depth": "basic",
        "include_answer": True,
    }).encode()
    req = urllib.request.Request(
        TAVILY_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return ""  # never fake facts on error — engine opens an Evidence gap
    lines: list[str] = []
    if data.get("answer"):
        lines.append("ANSWER: " + str(data["answer"]))
    for item in (data.get("results") or [])[:max_results]:
        lines.append(f"- {item.get('title','')}: "
                     f"{(item.get('content') or '')[:200]} ({item.get('url','')})")
    return "\n".join(lines)


def default_grounding() -> Callable[[str], str]:
    """Return a grounding function: Tavily if a key is present, else no-op."""
    if os.environ.get("TAVILY_API_KEY"):
        return lambda q: tavily_search(q)
    return lambda q: ""
