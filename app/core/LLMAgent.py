from __future__ import annotations

import os
from openai import OpenAI


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

        try: 
            prompt = (
                "You are a TTL classifier for a semantic cache.\n"
                "Your task is to classify the expected stability of the ANSWER to this specific query into one of the TTL buckets based on how quickly the information is expected to change.\n\n"

                "TTL buckets (return ONLY the number):\n"
                "- 3600  → Medium staleness risk. Information may change within a few hours or days.\n"
                "         Examples: recent announcements, this week’s updates, evolving situationsn"
                "- 10800 → Low-medium staleness risk. Information changes slowly but is not fully timeless.\n"
                "         Examples: summaries of prior events, comparisons, recent facts.\n"
                "- 43200 → Low staleness risk. Evergreen or mostly stable information.\n"
                "         Examples: definitions, explanations, how things work, historical facts.\n\n"

                "If unsure between two buckets, ALWAYS choose the shorter TTL.\n\n"
                f"User query: {query}"
            )

            completion = self._client.chat.completions.create(
                model="google/gemini-2.0-flash-exp",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return only one integer TTL in seconds. If the answer is expected to be stable for a long time, return 43200. "
                            "Valid outputs: 3600, 10800, 43200. "
                            "No explanations. No extra text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )

            raw = (completion.choices[0].message.content or "").strip()
            print(f"Raw TTL: {raw}")
            ttl = int(raw)
            return ttl if ttl in {3600, 10800, 43200} else 3600
        
        except ValueError:
            return 3600



