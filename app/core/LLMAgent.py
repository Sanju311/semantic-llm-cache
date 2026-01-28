from __future__ import annotations

import logging
import os
from openai import OpenAI

_logger = logging.getLogger(__name__)


class AIAgent:
    """Abstraction boundary for all AI calls (LLM + embeddings + TTL helper)."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required")

        self._client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    #Google: Gemini 2.5 Flash Lite
    def generate_response(self, query: str) -> str:
        completion = self._client.chat.completions.create(
            model="google/gemini-2.5-flash-lite",
            messages=[{"role": "user", "content": query}],
        )
        return (completion.choices[0].message.content or "").strip()

    #openai/text-embedding-3-small
    def embed_query(self, query: str) -> list[float]:
        embedding = self._client.embeddings.create(
            model="openai/text-embedding-3-small",
            input=query,
        )
        return embedding.data[0].embedding

    #Google: Gemini 2.0 Flash experimental
    def choose_ttl(self, query: str) -> int:
        prompt = (
            "You are a TTL classifier for a semantic cache.\n"
            "Pick exactly one TTL bucket for the user's query.\n\n"
            "TTL buckets (return ONLY the number):\n"
            "- 900   (15 minutes) high staleness risk\n"
            "- 3600  (1 hour)      medium staleness risk\n"
            "- 10800 (3 hours)     low-medium staleness risk\n"
            "- 43200 (12 hours)    low staleness risk\n\n"
            "If unsure, ALWAYS choose the shorter TTL.\n\n"
            f"User query: {query}"
        )
        completion = self._client.chat.completions.create(
            model="google/gemini-2.0-flash-exp",
            messages=[
                {"role": "system", "content": "Return only one integer TTL in seconds: 900, 3600, 10800, or 43200."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = (completion.choices[0].message.content or "").strip()
        try:
            ttl = int(raw)
        except ValueError:
            _logger.error("TTL parse failed: %r", raw)
            return 3600

        if ttl not in {900, 3600, 10800, 43200}:
            _logger.error("TTL out of range: %r", raw)
            return 3600
        return ttl



