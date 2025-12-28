"""더미 LLM 엔드포인트(OpenAI 호환 chat completions)입니다.

docker-compose.dev.yml에서 Django assistant 서비스를
실제 사내 LLM 게이트웨이를 호출하지 않고도 검증할 수 있도록 제공합니다.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

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


def _render_reply(question: str) -> str:
    template = (DUMMY_LLM_REPLY_TEMPLATE or "").strip()
    if not template:
        template = "개발용 더미 LLM 응답입니다. 질문: {question}"
    reply = template.replace("{question}", question)
    return reply.strip() or "개발용 더미 LLM 응답입니다."


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


@router.post("/v1/chat/completions")
@router.post("/{prefix:path}/v1/chat/completions")
async def chat_completions(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
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
    reply = _render_reply(question)
    return _build_chat_completion(model_name, reply)
