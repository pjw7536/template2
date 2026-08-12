# =============================================================================
# 모듈: 어시스턴트 API 뷰
# 주요 엔드포인트: AssistantRagIndexListView.get, AssistantChatView.post
# 주요 가정: parse_json_body는 실패 시 None을 반환합니다.
# =============================================================================
"""어시스턴트 채팅/인덱스 조회 엔드포인트 모음입니다."""
from __future__ import annotations

import json
import logging
from typing import Dict, List
from uuid import UUID

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from api.common.services import (
    extract_first_error_message,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from . import selectors
from .serializers import (
    AssistantChatRequestSerializer,
    AssistantConversationCreateSerializer,
    AssistantConversationExportQuerySerializer,
    AssistantConversationListQuerySerializer,
    AssistantConversationSummaryRequestSerializer,
    AssistantConversationSerializer,
    AssistantConversationUpdateSerializer,
    AssistantGenerationCreateSerializer,
    AssistantGenerationFinalizeSerializer,
    AssistantGenerationSerializer,
    AssistantMessageBatchSerializer,
    AssistantMessageFeedbackSerializer,
    AssistantMessageListQuerySerializer,
    AssistantMessageSerializer,
)
from .services import (
    AssistantConfigError,
    AssistantRequestError,
    AssistantGenerationBusyError,
    acquire_assistant_generation,
    append_user_prompt,
    append_assistant_messages,
    assistant_chat_service,
    build_rag_index_list_payload,
    build_assistant_csv_export,
    build_assistant_markdown_export,
    clear_assistant_messages,
    conversation_memory,
    create_assistant_conversation,
    delete_assistant_conversation,
    delete_assistant_message_feedback,
    finalize_assistant_generation,
    generate_assistant_conversation_title,
    normalize_history,
    normalize_room_id,
    normalize_segments,
    normalize_sources,
    request_openwebui_chat,
    refresh_assistant_conversation_summary,
    stream_openwebui_chat,
    update_assistant_conversation,
    upsert_assistant_message_feedback,
    resolve_permission_groups,
    resolve_rag_index_names,
    validate_user_identity,
)

logger = logging.getLogger(__name__)

OPENWEBUI_MEMORY_ROOM_PREFIX = "openwebui-"


class _AssistantEventStreamRenderer(JSONRenderer):
    """DRF 콘텐츠 협상에서 SSE 응답 media type을 허용합니다."""

    media_type = "text/event-stream"
    format = "sse"


def _conversation_not_found_response() -> JsonResponse:
    """소유하지 않거나 존재하지 않는 대화방을 동일한 404로 반환합니다."""

    return JsonResponse({"error": "대화방을 찾을 수 없습니다."}, status=404)


def _encode_sse_event(event: str, payload: object) -> str:
    """브라우저가 해석할 수 있는 UTF-8 SSE event 문자열을 생성합니다."""

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


def _get_conversation_summary(
    *,
    user: object,
    room_id: object,
    context_key: str,
) -> str:
    """현재 사용자의 대화방과 기억 그룹이 일치하는 장기 요약만 반환합니다."""

    try:
        conversation_id = UUID(str(room_id))
    except (TypeError, ValueError, AttributeError):
        return ""
    summary = selectors.get_assistant_conversation_summary_for_user(
        user=user,
        conversation_id=conversation_id,
        context_key=context_key,
    )
    return summary.summary if summary is not None else ""


def _build_recent_conversation_context(
    *,
    history: list[dict[str, str]],
    current_prompt: str,
    summary: str,
) -> str:
    """RAG 검색 질문과 분리해 LLM에만 전달할 이전 대화 문맥을 구성합니다."""

    recent = list(history)
    if (
        recent
        and recent[-1].get("role") == "user"
        and recent[-1].get("content") == current_prompt
    ):
        recent = recent[:-1]
    transcript = "\n".join(
        f"{'사용자' if item.get('role') == 'user' else 'Assistant'}: "
        f"{str(item.get('content') or '')[:800]}"
        for item in recent[-8:]
    )
    parts = []
    if summary:
        parts.append(f"장기 대화 요약:\n{summary}")
    if transcript:
        parts.append(f"최근 대화:\n{transcript}")
    return "\n\n".join(parts)


def _normalize_sources(raw_sources: object) -> List[Dict[str, str]]:
    """테스트에서 사용하는 normalize_sources 래퍼입니다.

    인자:
        raw_sources: 원본 출처 목록.

    반환:
        정규화된 출처 목록.

    부작용:
        없음. 순수 래퍼입니다.
    """

    return normalize_sources(raw_sources)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantRagIndexListView(APIView):
    """현재 사용자가 선택 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/assistant/rag-indexes

        반환:
            200: {
                예시 "ragIndexes": [...],
                예시 "defaultRagIndex": "...",
                예시 "emailRagIndex": "...",
                예시 "permissionGroups": [...],
                예시 "currentUserSdwtProd": "...",
                예시 "ragPublicGroup": "..."
            }

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            401: 비인증
            403: 권한 없음

        snake_case/camelCase 호환:
            입력 파라미터는 없으며, 응답 키는 camelCase로 반환합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 접근 가능한 인덱스/권한 그룹 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse(build_rag_index_list_payload(user=user))
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantChatView(APIView):
    """프론트엔드 어시스턴트 위젯에서 사용하는 채팅 엔드포인트."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """어시스턴트 채팅 요청을 처리하고 답변을 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/assistant/chat
            {
              예시 "prompt": "장비 점검 절차 알려줘",
              예시 "roomId": "room-1",
              예시 "permissionGroups": ["group-a"],
              예시 "ragIndexName": ["index-a"],
              예시 "history": [{"role": "user", "content": "이전 질문"}]
            }

        반환:
            200: {
              예시 "reply": "...",
              예시 "contexts": [...],
              예시 "sources": [...],
              예시 "segments": [...],
              예시 "meta": {"isDummy": false, "llmConfigured": true, "ragConfigured": true},
              예시 "echo": {"prompt": "...", "historyCount": 3, "username": "u", "roomId": "room-1"}
            }

        부작용:
            대화 이력이 캐시에 저장됩니다.

        오류:
            400: JSON/prompt/입력 형식 오류
            401: 비인증
            403: 권한 없음
            502: 업스트림 요청 실패 또는 응답 공백
            503: 어시스턴트 설정 누락

        snake_case/camelCase 호환:
            permissionGroups ↔ permission_groups, ragIndexName ↔ rag_index_name, roomId ↔ room_id를 모두 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 요청 본문 파싱 및 기본 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AssistantChatRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated_payload = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 2) 인증 및 사용자 식별자 검증
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        try:
            user_key, user_header_id = validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        # -----------------------------------------------------------------------------
        # 3) room_id/권한 그룹/인덱스 파싱
        # -----------------------------------------------------------------------------
        raw_room_id = validated_payload.get("room_id")
        room_id = normalize_room_id(raw_room_id)
        prompt_clean = validated_payload["prompt"]
        try:
            permission_groups = resolve_permission_groups(validated_payload, request.user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        try:
            rag_index_names = resolve_rag_index_names(validated_payload)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 히스토리 정규화 및 캐시 병합
        # -----------------------------------------------------------------------------
        incoming_history = normalize_history(
            validated_payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        history_with_prompt = append_user_prompt(
            incoming_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(user_key, room_id, history_with_prompt)
        conversation_summary = _get_conversation_summary(
            user=request.user,
            room_id=raw_room_id,
            context_key=validated_payload["context_key"],
        )

        # -----------------------------------------------------------------------------
        # 5) 어시스턴트 호출 및 응답 정규화
        # -----------------------------------------------------------------------------
        reply = ""
        contexts_used: List[str] = []
        sources_used: List[Dict[str, str]] = []
        segments_used: List[Dict[str, object]] = []
        is_dummy = False
        try:
            chat_result = assistant_chat_service.generate_reply(
                prompt_clean,
                user_header_id=user_header_id,
                rag_index_names=rag_index_names,
                permission_groups=permission_groups,
                conversation_context=_build_recent_conversation_context(
                    history=incoming_history,
                    current_prompt=prompt_clean,
                    summary=conversation_summary,
                ),
            )
            reply = chat_result.reply.strip() if isinstance(chat_result.reply, str) else ""
            contexts_used = chat_result.contexts
            sources_used = normalize_sources(getattr(chat_result, "sources", []))
            segments_used = normalize_segments(getattr(chat_result, "segments", []))
            is_dummy = getattr(chat_result, "is_dummy", False)
        except AssistantConfigError as exc:
            logger.error(
                "Assistant service configuration is missing required values.",
                extra={
                    "username": user_key,
                    "roomId": room_id,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url),
                    "ragConfigured": bool(assistant_chat_service.config.rag_url),
                },
                exc_info=exc,
            )
            return JsonResponse(
                {"error": "어시스턴트 API 설정이 누락되었습니다. 관리자에게 문의해주세요."},
                status=503,
            )
        except AssistantRequestError as exc:
            logger.exception(
                "Assistant upstream request failed",
                extra={"username": user_key, "roomId": room_id},
            )
            return JsonResponse({"error": str(exc)}, status=502)

        # -----------------------------------------------------------------------------
        # 6) 응답 검증 및 히스토리 업데이트
        # -----------------------------------------------------------------------------
        if not reply:
            logger.error(
                "Assistant reply is empty despite successful upstream call.",
                extra={"username": user_key, "roomId": room_id, "contextCount": len(contexts_used)},
            )
            return JsonResponse({"error": "어시스턴트 응답이 비어 있습니다. 관리자에게 문의해주세요."}, status=502)

        assistant_history_payload = (
            [{"role": "assistant", "content": segment["reply"]} for segment in segments_used]
            if segments_used
            else [{"role": "assistant", "content": reply}]
        )
        updated_history = conversation_memory.append(user_key, room_id, assistant_history_payload)

        logger.debug(
            "Assistant chat request received",
            extra={
                "historyCount": len(updated_history),
                "username": user_key,
                "roomId": room_id,
                "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                "contextCount": len(contexts_used),
                "sourceCount": len(sources_used),
                "isDummy": is_dummy,
            },
        )

        return JsonResponse(
            {
                "reply": reply,
                "contexts": contexts_used,
                "sources": sources_used,
                "segments": segments_used,
                "meta": {
                    "isDummy": is_dummy,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                    "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                },
                "echo": {
                    "prompt": prompt_clean,
                    "historyCount": len(updated_history),
                    "username": user_key,
                    "roomId": room_id,
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AssistantOpenWebUIChatView(APIView):
    """메일함 외 화면에서 사용하는 일반 OpenWebUI 채팅 엔드포인트."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """대화 이력을 OpenWebUI에 전달하고 기존 채팅 응답 형태로 반환합니다."""

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AssistantChatRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        validated_payload = serializer.validated_data
        try:
            user_key, _ = validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        raw_room_id = validated_payload.get("room_id")
        room_id = normalize_room_id(raw_room_id)
        memory_room_id = f"{OPENWEBUI_MEMORY_ROOM_PREFIX}{room_id}"
        prompt_clean = validated_payload["prompt"]
        incoming_history = normalize_history(
            validated_payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        history_with_prompt = append_user_prompt(
            incoming_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(user_key, memory_room_id, history_with_prompt)

        try:
            reply = request_openwebui_chat(
                history=history_with_prompt,
                conversation_summary=_get_conversation_summary(
                    user=request.user,
                    room_id=raw_room_id,
                    context_key=validated_payload["context_key"],
                ),
            )
        except AssistantConfigError as exc:
            logger.error(
                "Assistant OpenWebUI configuration is missing required values.",
                extra={"username": user_key, "roomId": room_id},
                exc_info=exc,
            )
            return JsonResponse(
                {"error": "OpenWebUI 설정이 누락되었습니다. 관리자에게 문의해주세요."},
                status=503,
            )
        except AssistantRequestError as exc:
            logger.exception(
                "Assistant OpenWebUI request failed",
                extra={"username": user_key, "roomId": room_id},
            )
            return JsonResponse({"error": str(exc)}, status=502)

        updated_history = conversation_memory.append(
            user_key,
            memory_room_id,
            [{"role": "assistant", "content": reply}],
        )
        return JsonResponse(
            {
                "reply": reply,
                "contexts": [],
                "sources": [],
                "segments": [],
                "meta": {
                    "provider": "openwebui",
                    "isDummy": False,
                    "llmConfigured": True,
                    "ragConfigured": False,
                },
                "echo": {
                    "prompt": prompt_clean,
                    "historyCount": len(updated_history),
                    "username": user_key,
                    "roomId": room_id,
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AssistantOpenWebUIStreamView(APIView):
    """일반 OpenWebUI 답변을 SSE delta로 전달합니다."""

    renderer_classes = [JSONRenderer, _AssistantEventStreamRenderer]

    def post(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> StreamingHttpResponse | JsonResponse:
        """OpenWebUI stream을 `meta`, `delta`, `done`, `error` event로 반환합니다.

        요청 예시:
            POST /api/v1/assistant/openwebui-chat/stream
            {"prompt": "DOWN 원인은?", "roomId": "...", "history": [...]}

        snake_case/camelCase 호환:
            기존 AssistantChatRequestSerializer 계약을 그대로 사용합니다.
        """

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AssistantChatRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        validated_payload = serializer.validated_data
        try:
            user_key, _ = validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        raw_room_id = validated_payload.get("room_id")
        room_id = normalize_room_id(raw_room_id)
        memory_room_id = f"{OPENWEBUI_MEMORY_ROOM_PREFIX}{room_id}"
        prompt_clean = validated_payload["prompt"]
        incoming_history = normalize_history(
            validated_payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        history_with_prompt = append_user_prompt(
            incoming_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(user_key, memory_room_id, history_with_prompt)

        def event_stream():
            """upstream iterator 수명과 SSE 연결 수명을 동일하게 유지합니다."""

            reply_parts: list[str] = []
            yield _encode_sse_event(
                "meta",
                {"provider": "openwebui", "ragConfigured": False},
            )
            try:
                for delta in stream_openwebui_chat(
                    history=history_with_prompt,
                    conversation_summary=_get_conversation_summary(
                        user=request.user,
                        room_id=raw_room_id,
                        context_key=validated_payload["context_key"],
                    ),
                ):
                    reply_parts.append(delta)
                    yield _encode_sse_event("delta", {"content": delta})

                reply = "".join(reply_parts).strip()
                if not reply:
                    raise AssistantRequestError("OpenWebUI 응답이 비어 있습니다.")
                updated_history = conversation_memory.append(
                    user_key,
                    memory_room_id,
                    [{"role": "assistant", "content": reply}],
                )
                yield _encode_sse_event(
                    "done",
                    {
                        "reply": reply,
                        "historyCount": len(updated_history),
                    },
                )
            except GeneratorExit:
                raise
            except (AssistantConfigError, AssistantRequestError) as exc:
                logger.warning(
                    "Assistant OpenWebUI stream 처리 실패: room_id=%s",
                    room_id,
                    exc_info=exc,
                )
                yield _encode_sse_event("error", {"error": str(exc)})

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationListCreateView(APIView):
    """현재 사용자의 대화방 목록 조회와 생성을 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 대화방 metadata를 최근 활동 순으로 반환합니다.

        예시 요청:
            GET /api/v1/assistant/conversations

        snake_case/camelCase 호환:
            입력 필드는 없고 응답은 camelCase입니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        query_serializer = AssistantConversationListQuerySerializer(data=request.GET)
        if not query_serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(query_serializer.errors)},
                status=400,
            )
        page = selectors.list_assistant_conversation_page(
            user=request.user,
            search=query_serializer.validated_data["search"],
            cursor_payload=query_serializer.validated_data["cursor_payload"],
            limit=query_serializer.validated_data["limit"],
            archived=query_serializer.validated_data["archived"],
        )
        return JsonResponse(
            {
                "results": AssistantConversationSerializer(page["results"], many=True).data,
                "nextCursor": page["nextCursor"],
                "hasMore": page["hasMore"],
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자 소유의 UUID 대화방을 생성합니다.

        예시 요청:
            POST /api/v1/assistant/conversations {"name": "새 대화"}

        snake_case/camelCase 호환:
            name 단일 필드를 사용하고 응답은 camelCase입니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantConversationCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        conversation = create_assistant_conversation(
            user=request.user,
            title=serializer.validated_data.get("name", "새 대화"),
        )
        return JsonResponse(
            AssistantConversationSerializer(conversation).data,
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationDetailView(APIView):
    """현재 사용자 소유 대화방의 metadata 갱신과 삭제를 제공합니다."""

    def patch(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """대화방 이름·고정·보관 상태 중 요청한 필드만 갱신합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantConversationUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        values = serializer.validated_data
        update_assistant_conversation(
            conversation=conversation,
            title=values.get("name"),
            pinned=values.get("pinned"),
            archived=values.get("archived"),
        )
        return JsonResponse(AssistantConversationSerializer(conversation).data)

    def delete(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """대화방과 모든 메시지를 cascade 삭제합니다.

        예시 요청:
            DELETE /api/v1/assistant/conversations/<uuid>

        snake_case/camelCase 호환:
            request body는 사용하지 않습니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        delete_assistant_conversation(conversation=conversation)
        return JsonResponse({}, status=204)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationTitleView(APIView):
    """현재 사용자 대화방의 OpenWebUI 제목 자동 생성을 제공합니다."""

    def post(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """저장된 최근 대화로 업무용 제목을 생성하고 대화방 metadata를 반환합니다.

        예시 요청:
            POST /api/v1/assistant/conversations/<uuid>/generate-title

        반환:
            200: {"id": "...", "name": "EQP DOWN 반복 원인 분석", ...}

        부작용:
            기본 이름인 대화방에서만 OpenWebUI를 호출하고 title을 저장합니다.

        오류:
            401: 비인증
            404: 소유하지 않거나 존재하지 않는 대화방
            409: 질문과 답변이 모두 저장되지 않음
            502: OpenWebUI 요청 또는 제목 응답 오류
            503: OpenWebUI 설정 누락

        snake_case/camelCase 호환:
            request body는 사용하지 않고 응답은 camelCase입니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        messages = selectors.list_recent_assistant_messages(
            conversation=conversation,
            limit=20,
        )
        try:
            titled_conversation = generate_assistant_conversation_title(
                conversation=conversation,
                messages=messages,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except AssistantConfigError as exc:
            logger.error(
                "Assistant 대화방 제목용 OpenWebUI 설정이 누락되었습니다.",
                extra={"conversationId": str(conversation_id)},
                exc_info=exc,
            )
            return JsonResponse(
                {"error": "OpenWebUI 설정이 누락되었습니다. 관리자에게 문의해주세요."},
                status=503,
            )
        except AssistantRequestError as exc:
            logger.warning(
                "Assistant 대화방 제목 생성에 실패했습니다: conversation_id=%s",
                conversation_id,
            )
            return JsonResponse({"error": str(exc)}, status=502)

        return JsonResponse(
            AssistantConversationSerializer(titled_conversation).data,
        )


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationSummaryView(APIView):
    """현재 사용자 대화방의 rolling summary 갱신을 제공합니다."""

    def post(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """충분한 과거 메시지가 쌓였을 때 장기 기억 요약을 갱신합니다.

        예시 요청:
            POST /api/v1/assistant/conversations/<uuid>/refresh-summary
            {"contextKey": "assistant:openwebui"}

        snake_case/camelCase 호환:
            contextKey/context_key를 지원하고 요약 갱신 metadata를 camelCase로 반환합니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        payload, parse_error = parse_json_body_or_error_when_present(request)
        if parse_error is not None:
            return parse_error
        serializer = AssistantConversationSummaryRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        context_key = serializer.validated_data["context_key"]
        batch = selectors.get_assistant_summary_batch(
            conversation=conversation,
            context_key=context_key,
        )
        messages = batch["messages"]
        if not messages:
            return JsonResponse(
                {
                    "updated": False,
                    "coveredMessageCount": batch["coveredMessageCount"],
                    "totalMessageCount": batch["totalMessageCount"],
                }
            )
        try:
            summary = refresh_assistant_conversation_summary(
                conversation=conversation,
                existing_summary=batch["summary"],
                messages=messages,
                covered_message_count=int(batch["coveredMessageCount"]),
                context_key=str(batch["contextKey"]),
            )
        except AssistantConfigError as exc:
            logger.warning("Assistant 장기 요약 설정이 누락되었습니다.", exc_info=exc)
            return JsonResponse({"error": str(exc)}, status=503)
        except AssistantRequestError as exc:
            logger.warning("Assistant 장기 요약 생성에 실패했습니다.", exc_info=exc)
            return JsonResponse({"error": str(exc)}, status=502)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        return JsonResponse(
            {
                "updated": True,
                "coveredMessageCount": summary.message_count,
                "totalMessageCount": batch["totalMessageCount"],
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationMessageView(APIView):
    """현재 사용자 대화방의 최근 메시지 조회와 멱등 추가를 제공합니다."""

    def get(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """대화방의 최근 메시지를 시간 오름차순으로 반환합니다.

        예시 요청:
            GET /api/v1/assistant/conversations/<uuid>/messages?limit=20

        snake_case/camelCase 호환:
            limit query만 받고 응답은 camelCase입니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        query_serializer = AssistantMessageListQuerySerializer(data=request.GET)
        if not query_serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(query_serializer.errors)},
                status=400,
            )
        cursor_payload = query_serializer.validated_data["cursor_payload"]
        if cursor_payload and cursor_payload.get("conversationId") != str(conversation_id):
            return JsonResponse(
                {"error": "before cursor와 현재 대화방이 일치하지 않습니다."},
                status=400,
            )
        page = selectors.list_assistant_message_page(
            conversation=conversation,
            cursor_payload=cursor_payload,
            limit=query_serializer.validated_data["limit"],
        )
        return JsonResponse(
            {
                "results": AssistantMessageSerializer(page["results"], many=True).data,
                "nextCursor": page["nextCursor"],
                "hasMore": page["hasMore"],
            }
        )

    def post(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """검증된 메시지 배열을 clientId 기준으로 중복 없이 저장합니다.

        예시 요청:
            POST /api/v1/assistant/conversations/<uuid>/messages
            {"messages": [{"clientId": "user-1", "role": "user", "content": "질문"}]}

        snake_case/camelCase 호환:
            clientId/client_id, contextKey/context_key, userSdwtProd/user_sdwt_prod를 지원합니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantMessageBatchSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        stored = append_assistant_messages(
            conversation=conversation,
            messages=serializer.validated_data["messages"],
        )
        return JsonResponse(
            {"results": AssistantMessageSerializer(stored, many=True).data},
            status=201,
        )

    def delete(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """대화방은 유지하고 저장된 메시지만 모두 삭제합니다.

        예시 요청:
            DELETE /api/v1/assistant/conversations/<uuid>/messages

        snake_case/camelCase 호환:
            request body는 사용하지 않습니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        clear_assistant_messages(conversation=conversation)
        return JsonResponse({}, status=204)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantGenerationListCreateView(APIView):
    """사용자 단위 활성 generation 조회와 lease 획득을 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 활성 generation이 있으면 반환합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        generation = selectors.get_active_assistant_generation_for_user(
            user=request.user,
        )
        return JsonResponse(
            {
                "generation": (
                    AssistantGenerationSerializer(generation).data
                    if generation is not None
                    else None
                )
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """다중 탭 중복 생성을 막는 사용자 단위 generation lease를 획득합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantGenerationCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        values = serializer.validated_data
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=values["conversation_id"],
        )
        if conversation is None:
            return _conversation_not_found_response()
        try:
            generation = acquire_assistant_generation(
                user=request.user,
                conversation=conversation,
                client_request_id=values["client_request_id"],
                context_key=values["context_key"],
                provider=values.get("provider", ""),
                model_name=values.get("model_name", ""),
            )
        except AssistantGenerationBusyError as exc:
            active = selectors.get_active_assistant_generation_for_user(
                user=request.user,
            )
            return JsonResponse(
                {
                    "error": str(exc),
                    "generation": (
                        AssistantGenerationSerializer(active).data
                        if active is not None
                        else None
                    ),
                },
                status=409,
            )
        return JsonResponse(AssistantGenerationSerializer(generation).data, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantGenerationDetailView(APIView):
    """사용자 소유 generation의 종료 상태 갱신을 제공합니다."""

    def patch(
        self,
        request: HttpRequest,
        generation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """generation을 완료·중단·실패 중 하나로 idempotent하게 종료합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        generation = selectors.get_assistant_generation_for_user(
            user=request.user,
            generation_id=generation_id,
        )
        if generation is None:
            return JsonResponse({"error": "생성 상태를 찾을 수 없습니다."}, status=404)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantGenerationFinalizeSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        generation = finalize_assistant_generation(
            generation=generation,
            **serializer.validated_data,
        )
        return JsonResponse(AssistantGenerationSerializer(generation).data)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantMessageFeedbackView(APIView):
    """Assistant 답변의 도움 여부 평가 저장과 취소를 제공합니다."""

    def put(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        client_id: str,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """현재 사용자 소유 Assistant 답변 평가를 생성하거나 교체합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        message = selectors.get_assistant_message_for_user(
            user=request.user,
            conversation_id=conversation_id,
            client_id=client_id,
        )
        if message is None:
            return JsonResponse({"error": "메시지를 찾을 수 없습니다."}, status=404)
        if message.role != message.Roles.ASSISTANT:
            return JsonResponse({"error": "Assistant 답변만 평가할 수 있습니다."}, status=400)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantMessageFeedbackSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        feedback = upsert_assistant_message_feedback(
            message=message,
            user=request.user,
            **serializer.validated_data,
        )
        return JsonResponse(
            {"rating": feedback.rating, "reason": feedback.reason},
        )

    def delete(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        client_id: str,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """현재 사용자 소유 메시지 평가를 취소합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        message = selectors.get_assistant_message_for_user(
            user=request.user,
            conversation_id=conversation_id,
            client_id=client_id,
        )
        if message is None:
            return JsonResponse({"error": "메시지를 찾을 수 없습니다."}, status=404)
        delete_assistant_message_feedback(message=message)
        return JsonResponse({}, status=204)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationExportView(APIView):
    """현재 활성 대화 분기의 Markdown·CSV 내보내기를 제공합니다."""

    def get(
        self,
        request: HttpRequest,
        conversation_id: UUID,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse | JsonResponse:
        """현재 분기만 UTF-8 Markdown 또는 Excel 호환 CSV로 반환합니다."""

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        conversation = selectors.get_assistant_conversation_for_user(
            user=request.user,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return _conversation_not_found_response()
        serializer = AssistantConversationExportQuerySerializer(
            data={"format": request.GET.get("exportFormat", "markdown")}
        )
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        messages = selectors.list_assistant_current_branch_messages(
            conversation=conversation,
        )
        export_format = serializer.validated_data["format"]
        if export_format == "csv":
            content = build_assistant_csv_export(
                conversation=conversation,
                messages=messages,
            )
            extension = "csv"
            content_type = "text/csv; charset=utf-8"
        else:
            content = build_assistant_markdown_export(
                conversation=conversation,
                messages=messages,
            )
            extension = "md"
            content_type = "text/markdown; charset=utf-8"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="assistant-{conversation.id}.{extension}"'
        )
        return response
