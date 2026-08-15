"""더미 LLM 엔드포인트(OpenAI 호환 chat completions)입니다.

docker-compose.dev.yml에서 Django assistant 서비스를
실제 사내 LLM 게이트웨이를 호출하지 않고도 검증할 수 있도록 제공합니다.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse

from adfs_settings import DUMMY_LLM_DELAY_MS, DUMMY_LLM_REPLY_TEMPLATE

router = APIRouter()

KNOWLEDGE_INTENT_TERMS = {
    "emails": (
        "메일",
        "이메일",
        "발신",
        "수신",
        "받은",
        "보낸",
        "제목",
        "첨부",
        "mail",
        "email",
    ),
    "appstore": ("앱", "app", "등록", "카테고리", "접근", "목록", "상태"),
    "line-dashboard": ("line", "라인", "상태", "이력", "집계", "알림", "수신"),
    "observer": ("observer", "장비", "로그", "분석", "이상", "원인", "변화", "근거"),
}
KNOWLEDGE_FOLLOW_UP_TERMS = (
    "그 ",
    "그거",
    "해당",
    "방금",
    "이전",
    "앞에서",
    "다시",
    "요약",
    "비교",
)


def _extract_latest_user_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""

    for entry in reversed(messages):
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "user":
            continue
        content = entry.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _extract_system_text(messages: Any) -> str:
    """더미 응답 계약 선택에 사용할 system message를 결합합니다."""

    if not isinstance(messages, list):
        return ""
    return "\n".join(
        str(entry.get("content") or "")
        for entry in messages
        if isinstance(entry, dict) and entry.get("role") == "system"
    )


def _render_knowledge_intent(question: str) -> str:
    """앱별 키워드와 최근 대화로 결정적인 지식 사용 판별 JSON을 만듭니다."""

    try:
        request_data = json.loads(question)
    except (json.JSONDecodeError, TypeError, ValueError):
        request_data = {}
    if not isinstance(request_data, dict):
        request_data = {}
    app_key = str(request_data.get("appKey") or "").strip()
    current_question = str(request_data.get("currentQuestion") or "").strip()
    recent_conversation = str(request_data.get("recentConversation") or "").strip()
    terms = KNOWLEDGE_INTENT_TERMS.get(app_key, ())
    lowered_question = current_question.casefold()
    lowered_context = recent_conversation.casefold()
    has_direct_term = any(term.casefold() in lowered_question for term in terms)
    follows_app_context = any(
        term.casefold() in lowered_question for term in KNOWLEDGE_FOLLOW_UP_TERMS
    ) and any(term.casefold() in lowered_context for term in terms)
    use_knowledge = bool(terms) and (has_direct_term or follows_app_context)
    return json.dumps(
        {
            "useKnowledge": use_knowledge,
            "searchQuery": current_question if use_knowledge else "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _render_auto_knowledge_route(question: str) -> str:
    """현재 앱 우선 규칙으로 결정적인 자동 지식 선택 JSON을 만듭니다."""

    try:
        request_data = json.loads(question)
    except (json.JSONDecodeError, TypeError, ValueError):
        request_data = {}
    if not isinstance(request_data, dict):
        request_data = {}
    active_app = str(request_data.get("activeApp") or "").strip()
    available_apps = [
        str(item).strip()
        for item in request_data.get("availableApps", [])
        if isinstance(item, str) and str(item).strip() in KNOWLEDGE_INTENT_TERMS
    ]
    current_question = str(request_data.get("currentQuestion") or "").strip()
    lowered_question = current_question.casefold()
    matched_apps = [
        app_key
        for app_key in available_apps
        if any(
            term.casefold() in lowered_question
            for term in KNOWLEDGE_INTENT_TERMS.get(app_key, ())
        )
    ]
    target_app = (
        active_app
        if active_app in matched_apps
        else (matched_apps[0] if matched_apps else "")
    )
    if not target_app:
        action = "general"
    elif target_app == active_app:
        action = "current_app"
    else:
        action = "other_app"
    return json.dumps(
        {"action": action, "targetApp": target_app, "scopeHints": {}},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _render_reply(question: str, messages: Any) -> str:
    """요청된 Provider 출력 계약과 일치하는 결정적 응답을 만듭니다."""

    template = (DUMMY_LLM_REPLY_TEMPLATE or "").strip()
    if not template:
        template = "개발용 더미 LLM 응답입니다. 질문: {question}"
    reply = template.replace("{question}", question)
    normalized_reply = reply.strip() or "개발용 더미 LLM 응답입니다."
    system_text = _extract_system_text(messages)
    if "전역 지식 선택 라우터" in system_text:
        return _render_auto_knowledge_route(question)
    if "지식 사용 라우터" in system_text:
        return _render_knowledge_intent(question)
    if "usedEmailIds" in system_text and '"segments"' in system_text:
        return json.dumps(
            {"answer": normalized_reply, "segments": []},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if "Observer 로그 분석기" in system_text:
        return json.dumps(
            {
                "headline": "개발용 Observer 분석",
                "summary": normalized_reply,
                "findings": [],
                "recommendedChecks": [],
                "limitations": ["개발용 더미 응답입니다."],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return normalized_reply


def _sleep_if_needed() -> None:
    delay_ms = max(0, int(DUMMY_LLM_DELAY_MS))
    if delay_ms:
        time.sleep(delay_ms / 1000.0)


def _build_chat_completion(model: str, reply: str) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _stream_chat_completion(model: str, reply: str):
    """개발 환경에서도 실제 OpenAI 호환 SSE chunk를 순서대로 반환합니다."""

    chunk_size = 8
    for index in range(0, len(reply), chunk_size):
        content = reply[index : index + chunk_size]
        payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
@router.post("/{prefix:path}/v1/chat/completions")
async def chat_completions(payload: Dict[str, Any] = Body(...)) -> Any:
    """결정적인 chat completion 응답을 반환합니다."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid JSON body")

    model = payload.get("model")
    model_name = model.strip() if isinstance(model, str) and model.strip() else "dummy-model"

    messages = payload.get("messages")
    question = _extract_latest_user_text(messages)
    if not question:
        raise HTTPException(status_code=400, detail="messages with a user prompt is required")

    _sleep_if_needed()
    reply = _render_reply(question, messages)
    if payload.get("stream") is True:
        return StreamingResponse(
            _stream_chat_completion(model_name, reply),
            media_type="text/event-stream",
        )
    return _build_chat_completion(model_name, reply)
