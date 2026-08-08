"""
Redis cache — caches query results and embeddings to reduce latency on repeat queries.
"""

import json
import hashlib
import logging
from typing import Optional, Any

from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Two-layer cache for the RepoPilot agent:
    1. Query cache: hash(question) → cached answer (TTL 1 hour)
    2. Embedding cache: hash(text) → embedding vector (TTL 24 hours)
    """

    QUERY_TTL = 3600  # 1 hour
    EMBEDDING_TTL = 86400  # 24 hours

    def __init__(self):
        self._client = None
        self._enabled = True

    def _get_client(self):
        """Lazy-initialize the Redis client."""
        if self._client is None:
            try:
                import redis

                self._client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                self._client.ping()
                logger.info(f"Redis connected: {settings.redis_url}")
            except Exception as e:
                logger.warning(
                    f"Redis connection failed (caching disabled): {e}"
                )
                self._enabled = False
        return self._client

    @staticmethod
    def _hash_key(prefix: str, text: str) -> str:
        """Generate a cache key from a prefix and text."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"repopilot:{prefix}:{text_hash}"

    # ── Query Cache ──────────────────────────────────────
    def get_cached_answer(self, question: str) -> Optional[dict]:
        """
        Check if we have a cached answer for this question.

        Returns:
            Cached response dict or None if not found.
        """
        if not self._enabled:
            return None

        try:
            client = self._get_client()
            if not client:
                return None

            key = self._hash_key("query", question.strip().lower())
            cached = client.get(key)

            if cached:
                logger.info(f"Cache HIT for question: {question[:50]}...")
                return json.loads(cached)

            logger.debug(f"Cache MISS for question: {question[:50]}...")
            return None

        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    def cache_answer(self, question: str, response: dict):
        """
        Cache an answer for a question.

        Args:
            question: The user's question.
            response: The full response dict to cache.
        """
        if not self._enabled:
            return

        try:
            client = self._get_client()
            if not client:
                return

            key = self._hash_key("query", question.strip().lower())
            client.setex(key, self.QUERY_TTL, json.dumps(response, default=str))
            logger.debug(f"Cached answer for: {question[:50]}...")

        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    # ── Embedding Cache ──────────────────────────────────
    def get_cached_embedding(self, text: str) -> Optional[list[float]]:
        """Get a cached embedding vector for a text chunk."""
        if not self._enabled:
            return None

        try:
            client = self._get_client()
            if not client:
                return None

            key = self._hash_key("embed", text)
            cached = client.get(key)

            if cached:
                return json.loads(cached)
            return None

        except Exception as e:
            logger.warning(f"Redis embedding get failed: {e}")
            return None

    def cache_embedding(self, text: str, embedding: list[float]):
        """Cache an embedding vector for a text chunk."""
        if not self._enabled:
            return

        try:
            client = self._get_client()
            if not client:
                return

            key = self._hash_key("embed", text)
            client.setex(key, self.EMBEDDING_TTL, json.dumps(embedding))

        except Exception as e:
            logger.warning(f"Redis embedding set failed: {e}")


# Singleton cache instance
cache = RedisCache()
