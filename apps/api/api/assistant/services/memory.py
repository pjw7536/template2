# =============================================================================
# 모듈: 어시스턴트 대화 메모리 캐시
# 주요 클래스: ConversationMemory
# 주요 가정: 캐시 키는 username+room_id 조합으로 유일합니다.
# =============================================================================
from __future__ import annotations

from typing import Dict, List

from django.core.cache import cache

from .constants import DEFAULT_HISTORY_LIMIT, HISTORY_CACHE_TTL
from .normalization import normalize_history


class ConversationMemory:
    """사용자별 대화 이력을 캐시에 저장/슬라이딩 윈도우로 관리합니다.

    부작용:
        Django cache에 읽기/쓰기 작업이 발생합니다.
    """

    def __init__(self, max_messages: int = DEFAULT_HISTORY_LIMIT, ttl_seconds: int = HISTORY_CACHE_TTL) -> None:
        """메모리 캐시 설정값을 초기화합니다.

        인자:
            max_messages: 저장할 최대 메시지 수.
            ttl_seconds: 캐시 TTL(초).
        """

        self.max_messages = max(1, max_messages)
        self.ttl_seconds = max(60, ttl_seconds)

    def _key(self, username: str, room_id: str) -> str:
        return f"assistant:history:{username}:{room_id}"

    def load(self, username: str, room_id: str) -> List[Dict[str, str]]:
        """캐시에서 대화 이력을 로드합니다.

        인자:
            username: 사용자 식별자.
            room_id: 대화방 식별자.

        반환:
            정규화된 대화 이력 리스트.

        부작용:
            캐시 읽기가 발생합니다.
        """

        stored = cache.get(self._key(username, room_id), [])
        return normalize_history(stored, limit=self.max_messages)

    def save(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """대화 이력을 정규화한 뒤 캐시에 저장합니다.

        인자:
            username: 사용자 식별자.
            room_id: 대화방 식별자.
            messages: 저장할 메시지 리스트.

        반환:
            저장된(정규화된) 메시지 리스트.

        부작용:
            캐시 쓰기가 발생합니다.
        """

        trimmed = normalize_history(messages, limit=self.max_messages)
        cache.set(self._key(username, room_id), trimmed, self.ttl_seconds)
        return trimmed

    def append(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """기존 이력에 메시지를 추가하고 저장합니다.

        인자:
            username: 사용자 식별자.
            room_id: 대화방 식별자.
            messages: 추가할 메시지 리스트.

        반환:
            업데이트된(정규화된) 메시지 리스트.

        부작용:
            캐시 읽기/쓰기가 발생합니다.
        """

        current = self.load(username, room_id)
        current.extend(normalize_history(messages, limit=self.max_messages))
        return self.save(username, room_id, current)


conversation_memory = ConversationMemory()
