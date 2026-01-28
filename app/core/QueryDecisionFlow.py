from __future__ import annotations
import uuid

from app.core.CacheRepository import CacheRepository
from app.core.LLMAgent import AIAgent


class QueryDecisionFlow:
    """
    Orchestrates query handling.
    This class owns decision-making only.
    """

    def __init__(self, cache: CacheRepository, ai: AIAgent) -> None:
        self._cache = cache
        self._ai = ai
        self._similarity_threshold = 0.9

    def handle_query(self, query: str) -> dict:

        #assess query staleness risk
        risk_level = self.assess_query_staleness_risk(query)

        #check and return response from l1 cache if risk level is not high
        if risk_level != "high":
            response = self._cache.get("l1", query)
            if response is not None:
                return {"response": response, "metadata": {"source": "cache", "risk_level": risk_level}}

        #if l1 cache miss, embed query
        embedding = self._ai.embed_query(query)
        
        #return best match in l2 cache from top k = 5 results from (ANN search using cosine similarity evaluation)
        knn = self._cache.knn_search(embedding, k=5)

        #if best match has high similarity score, return response from l2 cache

        #TODO: add weighting for medium risk level
        if knn is not None and risk_level != "high":
            cache_id, similarity_score = knn
            cached_response = self._cache.get("l2", cache_id)
            
            print(f"Cached response: {cached_response} has similarity score: {similarity_score}")
            
            if similarity_score > self._similarity_threshold:
                response = self._cache.get("l2", cache_id)
                if response is not None:
                    return {"response": response, "metadata": {"source": "cache", "similarity_score": similarity_score}}

        #if closest match has low similarity score, return response from LLM
        response = self._ai.generate_response(query)
        return {
            "response": response,
            "metadata": {"source": "llm", "risk_level": risk_level, "similarity_score": similarity_score},
            "_embedding": embedding,
        }


    def assess_query_staleness_risk(self, query: str) -> str:

        formatted_query = query.lower()

        high_risk_words = [
            "today", "now", "current", "latest", "recent", "live",
            "at the moment", "immediate", "last", "status"
        ]

        medium_risk_words = [
            "yesterday", "last week", "last month", "this week", "trend", "previous"
        ]

        for word in high_risk_words:
            if word in formatted_query:
                return "high"
        for word in medium_risk_words:
            if word in formatted_query:
                return "medium"
        
        return "low"


    def async_write_to_caches(self, query: str, response: str, embedding: list[float]) -> None:

        ttl = self._ai.choose_ttl(query)
        self._cache.set("l1", query, response, ttl)

        new_cache_id = uuid.uuid4().hex
        self._cache.set("l2", new_cache_id, response, ttl)

        self._cache.upsert_vector(new_cache_id, embedding, ttl)



    

