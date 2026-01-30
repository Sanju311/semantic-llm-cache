from __future__ import annotations

import logging
import time
import uuid

from app.core.CacheService import CacheService
from app.core.LLMService import LLMService

_logger = logging.getLogger(__name__)


class QueryService:
    """
    Orchestrates query handling.
    This class owns decision-making only.
    """

    def __init__(self, cache: CacheService, ai: LLMService) -> None:
        self._cache = cache
        self._ai = ai
        self._similarity_threshold = 0.9

    def handle_query(self, query: str, force_refresh: bool = False) -> dict:
        _logger.info("Handling query (force_refresh=%s): %s", force_refresh, query)

        start = time.perf_counter()

        #assess query staleness risk
        risk_level = self.assess_query_staleness_risk(query)

        _logger.info("Risk level: %s", risk_level)

        #if force refresh is true, generate response from LLM
        if force_refresh or risk_level == "high":
            response = self._ai.generate_response(query)
            latency_ms = self._cache.record_outcome("llm", start, f"LLM response (force_refresh risk={risk_level})")

            #if risk level is high, then we don't write to cache as we don't want to persist
            if risk_level == "high":
                return {
                    "response": response,
                    "metadata": {"source": "llm", "risk_level": risk_level, "force_refresh": force_refresh, "latency_ms": latency_ms},
                }

            # For force_refresh low-risk, embedding is only needed for async writes (no decision depends on it).
            return {
                "response": response,
                "metadata": {"source": "llm", "risk_level": risk_level, "force_refresh": force_refresh, "latency_ms": latency_ms},
            }

        #check and return response from l1 cache
        response = self._cache.get("l1", query)
        if response is not None:
            latency_ms = self._cache.record_outcome("l1", start, f"L1 hit (risk={risk_level})")
            return {"response": response, "metadata": {"source": "cache", "cache_type": "l1", "risk_level": risk_level, "latency_ms": latency_ms}}


        #if l1 cache miss, embed query
        embedding = self._ai.embed_query(query)
        
        #return best match in l2 cache from top k = 5 results from (ANN search using cosine similarity evaluation)
        knn = self._cache.knn_search(embedding, k=5)

        _logger.info("knn returned from ANN search: %s", knn)    
        similarity_score = None
        closest_query = None

        #if best match has high similarity score, return response from l2 cache

        if knn is not None:
            cache_id, similarity_score = knn
            closest_query = self._cache.get_vector_query(cache_id)
            cached_response = self._cache.get("l2", cache_id)

            _logger.info("semantically closest query: %s", closest_query)
                
            if cached_response and similarity_score > self._similarity_threshold:
                latency_ms = self._cache.record_outcome("l2", start, f"L2 hit (score={similarity_score:.4f})")
                return {
                    "response": cached_response,
                    "metadata": {
                        "source": "cache",
                        "cache_type": "l2",
                        "risk_level": risk_level,
                        "cache_id": cache_id,
                        "similarity_score": similarity_score,
                        "closest_query": closest_query,
                        "latency_ms": latency_ms,
                    },
                }

        #if closest match has low similarity score, return response from LLM
        response = self._ai.generate_response(query)
        latency_ms = self._cache.record_outcome("llm", start, f"LLM response (risk={risk_level})")

        return {
            "response": response,
            "metadata": {
                "source": "llm",
                "risk_level": risk_level,
                "similarity_score": similarity_score,
                "closest_query": closest_query,
                "latency_ms": latency_ms,
            },
            "_embedding": embedding,
        }


    def assess_query_staleness_risk(self, query: str) -> str:
        formatted_query = query.lower()

        high_risk_words = [
            "today", "now", "current", "latest", "recent", "live",
            "at the moment", "immediate", "last", "status", "recent", "this week", "yesterday"
        ]

        for word in high_risk_words:
            if word in formatted_query:
                return "high"
        
        return "low"


    #write to all caches when query is from LLM and risk level is not high
    def async_write_to_cache(
        self,
        query: str,
        response: str,
        metadata: dict[str, object],
        embedding: list[float] | None = None,
    ) -> None:
        try:
            source = metadata.get("source")
            risk_level = metadata.get("risk_level")
            cache_type = metadata.get("cache_type")
            cache_id = metadata.get("cache_id")

            # Write to caches for LLM responses (embed if missing).
            if source == "llm" and risk_level != "high":
                if embedding is None:
                    embedding = self._ai.embed_query(query)
                ttl = self._ai.choose_ttl(query)
                _logger.info("LLM helper determined TTL as: %s", ttl)

                self._cache.set("l1", query, response, ttl)

                new_cache_id = uuid.uuid4().hex
                self._cache.set("l2", new_cache_id, response, ttl)
                self._cache.upsert_vector(new_cache_id, query, embedding, ttl)
                _logger.info("Async cache write complete (ttl=%s cache_id=%s)", ttl, new_cache_id)
                return

            #write to l1 cache from l2 cache (with same remaining ttl) to prevent future ANN search
            if source == "cache" and cache_type == "l2" and isinstance(cache_id, str) and cache_id:
                ttl = self._cache.get_ttl("l2", cache_id)
                if ttl is None:
                    return
                self._cache.set("l1", query, response, ttl)
                _logger.info("Promoted L2->L1 for query (ttl=%s cache_id=%s)", ttl, cache_id)
                return
        except Exception as e:
            _logger.exception("Async cache write failed: %s", e)



    

