"""LLM assistant 채팅용 임시 엔드포인트."""
from __future__ import annotations

import logging
from typing import Dict, List

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from .utils import parse_json_body

logger = logging.getLogger(__name__)


def _normalize_history(raw_history: object) -> List[Dict[str, str]]:
    """history 배열에서 role/content가 있는 메시지만 정규화."""

    normalized: List[Dict[str, str]] = []
    if not isinstance(raw_history, list):
        return normalized

    for entry in raw_history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue

        role_clean = role.strip()
        content_clean = content.strip()
        if role_clean and content_clean:
            normalized.append({"role": role_clean, "content": content_clean})

        if len(normalized) >= 20:
            break

    return normalized


def _build_dummy_reply(prompt: str, history: List[Dict[str, str]]) -> str:
    """LLM 백엔드 연동 전 간단한 에코 응답 생성."""

    prompt_clean = prompt.strip()
    context_hint = history[-1]["content"] if history else None

    if context_hint:
        return (
            f"임시 응답입니다. 마지막 메시지({history[-1]['role']})를 참고해 "
            f"\"{prompt_clean}\" 질문을 확인했어요."
        )

    return f"임시 응답입니다. \"{prompt_clean}\" 질문을 확인했어요."


@method_decorator(csrf_exempt, name="dispatch")
class AssistantChatView(APIView):
    """프론트엔드 어시스턴트 위젯에서 사용하는 채팅 엔드포인트."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return JsonResponse({"error": "prompt is required"}, status=400)

        history = _normalize_history(payload.get("history"))
        reply = _build_dummy_reply(prompt, history)

        logger.debug("Assistant chat request received", extra={"historyCount": len(history)})

        return JsonResponse(
            {
                "reply": reply,
                "echo": {
                    "prompt": prompt.strip(),
                    "historyCount": len(history),
                },
            }
        )
