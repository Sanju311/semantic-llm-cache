from __future__ import annotations

import logging
import struct
from typing import Literal, Optional

from redis.commands.search.field import TagField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import ResponseError

import time

_logger = logging.getLogger(__name__)

class CacheService:
    """Data access layer for Redis-backed caches (L1, L2, and metrics)."""

    CacheType = Literal["l1", "l2", "metrics"]

    _VECTOR_INDEX = "idx:cache_vectors"
    _VECTOR_PREFIX = "vec:"
    _VECTOR_FIELD = "embedding"
    _CACHE_ID_FIELD = "cache_id"
    _QUERY_FIELD = "query"
    _EMBED_DIM = 1536  # openai/text-embedding-3-small

    def __init__(self, redis_client) -> None:
        self._redis = redis_client
        self._vector = self._redis.ft(self._VECTOR_INDEX)
        self._create_vector_index()

    def get(self, cache_type: CacheType, key: str) -> Optional[str]:
        value = self._redis.get(self._format_key(cache_type, key))
        return value if value is not None else None

    def set(self, cache_type: CacheType, key: str, value: str, ttl: int) -> None:
        self._redis.set(self._format_key(cache_type, key), value, ex=ttl)

    def get_ttl(self, cache_type: CacheType, key: str) -> Optional[int]:
        value = self._redis.ttl(self._format_key(cache_type, key))
        if value is None or value < 0:
            return None
        return int(value)

    #returns best match given 3 results from ANN search
    def knn_search(self, embedding: list[float], k: int = 3) -> Optional[tuple[str, float]]:

        packed = self._pack_vector(embedding)
        q = (
            Query(f"*=>[KNN {k} @{self._VECTOR_FIELD} $vec AS distance]")
            .return_fields(self._CACHE_ID_FIELD, "distance")
            .sort_by("distance")
            .dialect(2)
        )
        try:
            res = self._vector.search(q, query_params={"vec": packed})
        except ResponseError as e:
            _logger.error("Vector search failed: %s", e)
            raise
        if not res.docs:
            return None

        best = res.docs[0]
        return best.cache_id, 1 - float(best.distance)

    def incr_metric(self, name: str, amount: int | float = 1) -> None:
        key = self._format_key("metrics", name)
        if isinstance(amount, int) and not isinstance(amount, bool):
            self._redis.incrby(key, amount)
            return
        self._redis.incrbyfloat(key, float(amount))

    def flush_all(self) -> None:
        self._redis.flushdb()
        self._vector = self._redis.ft(self._VECTOR_INDEX)
        self._create_vector_index()
        _logger.info("Redis DB flushed and vector index recreated: %s", self._VECTOR_INDEX)

    def record_outcome(self, outcome: Literal["l1", "l2", "llm"], start: float, message: str) -> float:
        latency_ms = (time.perf_counter() - start) * 1000
        self.incr_metric(f"{outcome}_latency_ms_sum", latency_ms)
        self.incr_metric(f"{outcome}_calls_total", 1)
        _logger.info("%s %.2fms", message, latency_ms)
        return latency_ms

    def upsert_vector(self, cache_id: str, query: str, embedding: list[float], ttl: int) -> None:
        key = f"{self._VECTOR_PREFIX}{cache_id}"
        self._redis.hset(
            key,
            mapping={
                self._CACHE_ID_FIELD: cache_id,
                self._QUERY_FIELD: query,
                self._VECTOR_FIELD: self._pack_vector(embedding),
            },
        )
        self._redis.expire(key, ttl)

    def get_vector_query(self, cache_id: str) -> Optional[str]:
        key = f"{self._VECTOR_PREFIX}{cache_id}"
        value = self._redis.hget(key, self._QUERY_FIELD)
        return value if value is not None else None

    def get_metrics(self) -> dict:
        keys = [
            "l1_latency_ms_sum",
            "l2_latency_ms_sum",
            "llm_latency_ms_sum",
            "l1_calls_total",
            "l2_calls_total",
            "llm_calls_total",
        ]
        return {k: self.get("metrics", k) for k in keys}

    @staticmethod
    def _format_key(cache_type: CacheType, key: str) -> str:
        return f"{cache_type}:{key}"

    def _create_vector_index(self) -> None:
        schema = [
            TagField(self._CACHE_ID_FIELD),
            VectorField(
                self._VECTOR_FIELD,
                "HNSW",
                {
                    "TYPE": "FLOAT32",
                    "DIM": self._EMBED_DIM,
                    "DISTANCE_METRIC": "COSINE",
                },
            ),
        ]
        definition = IndexDefinition(prefix=[self._VECTOR_PREFIX], index_type=IndexType.HASH)
        try:
            self._vector.create_index(schema, definition=definition)
        except ResponseError as e:
            if "Index already exists" in str(e):
                _logger.info("Vector index already exists: %s", self._VECTOR_INDEX)
                return
            _logger.error("Vector index create failed: %s", e)
            raise

    def _pack_vector(self, embedding: list[float]) -> bytes:
        if len(embedding) != self._EMBED_DIM:
            raise ValueError(f"Expected embedding dim {self._EMBED_DIM}, got {len(embedding)}")
        return struct.pack(f"{self._EMBED_DIM}f", *embedding)
