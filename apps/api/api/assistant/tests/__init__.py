# =============================================================================
# 모듈: 어시스턴트 기능 테스트
# 주요 대상: RAG 인덱스 조회, 채팅 권한 검증, 응답/정규화 처리
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import csv
import json
import threading
import time
from datetime import timedelta
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve
from django.utils import timezone

import api.account.services as account_services
from api.assistant import selectors as assistant_selectors
from api.assistant import services as assistant_services
from api.assistant.models import (
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantConversationSummary,
    AssistantGeneration,
    AssistantMessage,
    AssistantMessageFeedback,
)
from api.assistant.services import (
    AssistantChatConfig,
    AssistantChatService,
    AssistantConfigError,
    AssistantOpenWebUIConfig,
    build_openwebui_app_system_message,
    build_openwebui_grounded_system_message,
    build_openwebui_messages,
    normalize_openwebui_conversation_title,
    request_openwebui_chat,
    request_openwebui_conversation_title,
)
import api.rag.services as rag_services
from api.common.services import ExternalCallCancellation, ExternalCallCancelled


class RemovedAssistantCompatibilityRoutesTests(SimpleTestCase):
    """삭제한 Assistant 실행·저장 호환 경로가 다시 등록되지 않게 보장합니다."""

    def test_removed_routes_do_not_resolve(self) -> None:
        """표준 Turn 외 과거 실행·Generation 경로는 404여야 합니다."""

        paths = (
            "/api/v1/assistant/chat",
            "/api/v1/assistant/openwebui-chat",
            "/api/v1/assistant/openwebui-chat/stream",
            "/api/v1/assistant/generations",
            "/api/v1/assistant/generations/00000000-0000-0000-0000-000000000001",
        )
        for path in paths:
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)


def _set_current_affiliation(user, *, user_sdwt_prod: str) -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    account_services.set_current_affiliation_for_user(
        user=user,
        department="Dept",
        line="Line",
        user_sdwt_prod=user_sdwt_prod,
    )


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    for target in (
        "api.account.services.get_access_payload",
        "api.account.services.data_scope.get_access_payload",
    ):
        patcher = patch(target, return_value={"allowed": True})
        patcher.start()
        test_case.addCleanup(patcher.stop)


def _append_assistant_messages(
    *,
    conversation: AssistantConversation,
    messages: list[dict[str, object]],
) -> list[AssistantMessage]:
    """테스트 메시지에 현재 Assistant 권한 요구사항을 명시해 저장합니다."""

    prepared_messages = []
    for message in messages:
        context_key = str(
            message.get("context_key") or "assistant:openwebui:portal"
        )
        if context_key == "assistant":
            profile_key, memory_partition = "email-rag", "scope:emails"
        elif context_key.startswith("observer:"):
            profile_key, memory_partition = "observer-analysis", "scope:observer"
        else:
            profile_key, memory_partition = "portal-default", "shared"
        requirements = assistant_services.access_requirements_for_scopes(
            ("assistant",)
        )
        generation = AssistantGeneration.objects.create(
            user=conversation.user,
            conversation=conversation,
            client_request_id=f"test-{message['client_id']}",
            context_key=context_key,
            status=AssistantGeneration.Status.COMPLETED,
            provider="test",
            profile_key=profile_key,
            profile_version=2,
            memory_partition=memory_partition,
            access_requirements=requirements,
            expires_at=timezone.now() + timedelta(minutes=5),
            finished_at=timezone.now(),
        )
        prepared_messages.append(
            {
                **message,
                "context_key": context_key,
                "generation_id": generation.id,
                "access_requirements": requirements,
            }
        )
    return assistant_services.append_assistant_messages(
        conversation=conversation,
        messages=prepared_messages,
    )



__all__ = [name for name in globals() if not name.startswith("__")]
