from __future__ import annotations

from typing import Dict, List

from django.core.cache import cache

from .constants import DEFAULT_HISTORY_LIMIT, HISTORY_CACHE_TTL
from .normalization import normalize_history


class ConversationMemory:
    """사용자별 대화 이력을 캐시에 저장/슬라이딩 윈도우로 관리.

    Side effects:
        Reads/writes Django cache.
    """

    def __init__(self, max_messages: int = DEFAULT_HISTORY_LIMIT, ttl_seconds: int = HISTORY_CACHE_TTL) -> None:
        self.max_messages = max(1, max_messages)
        self.ttl_seconds = max(60, ttl_seconds)

    def _key(self, username: str, room_id: str) -> str:
        return f"assistant:history:{username}:{room_id}"

    def load(self, username: str, room_id: str) -> List[Dict[str, str]]:
        stored = cache.get(self._key(username, room_id), [])
        return normalize_history(stored, limit=self.max_messages)

    def save(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        trimmed = normalize_history(messages, limit=self.max_messages)
        cache.set(self._key(username, room_id), trimmed, self.ttl_seconds)
        return trimmed

    def append(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        current = self.load(username, room_id)
        current.extend(normalize_history(messages, limit=self.max_messages))
        return self.save(username, room_id, current)


conversation_memory = ConversationMemory()
