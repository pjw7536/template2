# =============================================================================
# 모듈: Assistant 대화방 권한 인식 목록·검색
# 주요 함수: list_accessible_assistant_conversation_page
# 핵심 전제: 잠긴 제목과 본문은 검색 predicate와 pagination에 사용하지 않습니다.
# =============================================================================
"""현재 권한으로 노출 가능한 대화 내용만 사용해 목록 검색 결과를 만듭니다."""

from __future__ import annotations

from typing import Any

from .. import selectors
from ..models import AssistantConversation
from .access_requirements import validate_access_requirements


def _title_matches(
    *,
    conversation: AssistantConversation,
    search: str,
    user: Any,
    request: Any,
) -> bool:
    """현재 노출 가능한 제목에 검색어가 포함되는지 반환합니다."""

    if conversation.title_source not in {"default", "user"}:
        decision = validate_access_requirements(
            user=user,
            requirements=conversation.title_access_requirements,
            request=request,
        )
        if not decision.allowed:
            return False
    return search in conversation.title.casefold()


def _body_matches(
    *,
    conversation: AssistantConversation,
    search: str,
    user: Any,
    request: Any,
) -> bool:
    """현재 branch의 접근 가능한 메시지 본문에 검색어가 있는지 반환합니다."""

    for message in selectors.list_assistant_current_branch_messages(
        conversation=conversation
    ):
        decision = validate_access_requirements(
            user=user,
            requirements=message.access_requirements,
            request=request,
        )
        if decision.allowed and search in message.content.casefold():
            return True
    return False


def list_accessible_assistant_conversation_page(
    *,
    user: Any,
    request: Any,
    search: str,
    cursor_payload: dict[str, object] | None,
    limit: int,
    archived: bool,
) -> dict[str, object]:
    """권한 검증을 검색보다 먼저 적용한 cursor 대화방 page를 반환합니다."""

    normalized_search = search.casefold()
    matching_ids = None
    if normalized_search:
        matching_ids = {
            conversation.id
            for conversation in selectors.list_assistant_conversations_for_user(
                user=user,
                archived=archived,
            )
            if _title_matches(
                conversation=conversation,
                search=normalized_search,
                user=user,
                request=request,
            )
            or _body_matches(
                conversation=conversation,
                search=normalized_search,
                user=user,
                request=request,
            )
        }
    return selectors.list_assistant_conversation_page(
        user=user,
        search=search,
        cursor_payload=cursor_payload,
        limit=limit,
        archived=archived,
        matching_conversation_ids=matching_ids,
    )


__all__ = ["list_accessible_assistant_conversation_page"]
