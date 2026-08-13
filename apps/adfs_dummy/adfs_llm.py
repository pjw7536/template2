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


def _render_reply(question: str, messages: Any) -> str:
    """요청된 Provider 출력 계약과 일치하는 결정적 응답을 만듭니다."""

    template = (DUMMY_LLM_REPLY_TEMPLATE or "").strip()
    if not template:
        template = "개발용 더미 LLM 응답입니다. 질문: {question}"
    reply = template.replace("{question}", question)
    normalized_reply = reply.strip() or "개발용 더미 LLM 응답입니다."
    system_text = _extract_system_text(messages)
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
