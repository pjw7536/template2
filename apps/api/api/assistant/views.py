# =============================================================================
# 모듈: 어시스턴트 API 뷰
# 주요 엔드포인트: AssistantTurnStreamView.post, AssistantRagIndexListView.get
# 주요 가정: parse_json_body는 실패 시 None을 반환합니다.
# =============================================================================
"""표준 Turn과 대화·인덱스 조회 엔드포인트 모음입니다."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

import api.account.services as account_services

from api.common.services import (
    extract_first_error_message,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from . import selectors
from .serializers import (
    AssistantConversationCreateSerializer,
    AssistantConversationExportQuerySerializer,
    AssistantConversationListQuerySerializer,
    AssistantConversationSummaryRequestSerializer,
    AssistantConversationSerializer,
    AssistantConversationUpdateSerializer,
    AssistantMessageFeedbackSerializer,
    AssistantMessageListQuerySerializer,
    AssistantMessageSerializer,
    AssistantTurnRequestSerializer,
)
from .services import (
    AssistantConfigError,
    AssistantRequestError,
    build_rag_index_list_payload,
    build_assistant_csv_export,
    build_assistant_markdown_export,
    clear_assistant_messages,
    create_assistant_conversation,
    delete_assistant_conversation,
    delete_assistant_message_feedback,
    generate_assistant_conversation_title,
    list_accessible_assistant_conversation_page,
    refresh_authorized_assistant_conversation_summary,
    update_assistant_conversation,
    upsert_assistant_message_feedback,
    AssistantProfileUnavailableError,
    AssistantTurnError,
    assistant_turn_service,
    validate_access_requirements,
)

logger = logging.getLogger(__name__)


class _AssistantEventStreamRenderer(JSONRenderer):
    """DRF 콘텐츠 협상에서 SSE 응답 media type을 허용합니다."""

    media_type = "text/event-stream"
    format = "sse"


@method_decorator(csrf_exempt, name="dispatch")
class AssistantTurnStreamView(APIView):
    """versioned Profile 기반 표준 Assistant Turn을 SSE로 실행합니다."""

    renderer_classes = [JSONRenderer, _AssistantEventStreamRenderer]

    def post(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> StreamingHttpResponse | JsonResponse:
        """send/edit/regenerate/retry와 완료 Run replay를 표준 event로 반환합니다.

        예시 요청:
            POST /api/v1/assistant/turns/stream
            {"action":"send","conversationId":"<uuid>",
             "clientRequestId":"request-1","profileKey":"portal-default",
             "message":{"clientId":"user-1","content":"질문"},"toolInputs":{}}

        오류:
            연결 전 입력·권한·idempotency 오류는 JSON 4xx, 연결 후 실행 오류는 SSE입니다.
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AssistantTurnRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "error": "invalid_request",
                    "message": extract_first_error_message(serializer.errors),
                },
                status=400,
            )
        try:
            prepared = assistant_turn_service.prepare_turn(
                user=request.user,
                request=request,
                values=serializer.validated_data,
            )
        except AssistantTurnError as exc:
            response_payload: dict[str, object] = {
                "error": exc.code,
                "message": exc.message,
            }
            if exc.missing_scopes:
                response_payload["missingScopes"] = list(exc.missing_scopes)
            return JsonResponse(response_payload, status=exc.status_code)
        except AssistantProfileUnavailableError:
            return JsonResponse(
                {"error": "profile_version_unavailable"},
                status=409,
            )
        except ValueError as exc:
            return JsonResponse(
                {"error": "invalid_request", "message": str(exc)},
                status=400,
            )

        def event_stream():
            """Turn event iterator를 UTF-8 SSE frame으로 변환합니다."""

            for event, event_payload in assistant_turn_service.stream_turn(
                prepared=prepared,
                request=request,
            ):
                yield _encode_sse_event(event, event_payload)

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response


def _conversation_not_found_response() -> JsonResponse:
    """소유하지 않거나 존재하지 않는 대화방을 동일한 404로 반환합니다."""

    return JsonResponse({"error": "대화방을 찾을 수 없습니다."}, status=404)


def _require_account_scopes(
    *,
    request: HttpRequest,
    scopes: tuple[str, ...],
) -> JsonResponse | None:
    """현재 Account 앱 scope가 하나라도 없으면 안전한 403 응답을 반환합니다."""

    missing = [
        scope
        for scope in scopes
        if not account_services.get_access_payload(
            user=request.user,
            scope_key=scope,
            request=request,
        ).get("allowed")
    ]
    if not missing:
        return None
    return JsonResponse(
        {"error": "permission_denied", "missingScopes": missing},
        status=403,
    )


def _message_access_denied(*, request: HttpRequest, message: object) -> bool:
    """메시지의 현재 access requirements가 회수됐는지 반환합니다."""

    return not validate_access_requirements(
        user=request.user,
        requirements=getattr(message, "access_requirements", {}),
        request=request,
    ).allowed


def _encode_sse_event(event: str, payload: object) -> str:
    """브라우저가 해석할 수 있는 UTF-8 SSE event 문자열을 생성합니다."""

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


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

        요청/응답 계약:
            입력 파라미터는 없으며, 응답 키는 camelCase로 반환합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        permission_error = _require_account_scopes(
            request=request,
            scopes=("assistant", "emails"),
        )
        if permission_error is not None:
            return permission_error

        # -----------------------------------------------------------------------------
        # 2) 접근 가능한 인덱스/권한 그룹 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse(build_rag_index_list_payload(user=user))
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationListCreateView(APIView):
    """현재 사용자의 대화방 목록 조회와 생성을 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 대화방 metadata를 최근 활동 순으로 반환합니다.

        예시 요청:
            GET /api/v1/assistant/conversations

        요청/응답 계약:
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
        page = list_accessible_assistant_conversation_page(
            user=request.user,
            request=request,
            search=query_serializer.validated_data["search"],
            cursor_payload=query_serializer.validated_data["cursor_payload"],
            limit=query_serializer.validated_data["limit"],
            archived=query_serializer.validated_data["archived"],
        )
        return JsonResponse(
            {
                "results": AssistantConversationSerializer(
                    page["results"], many=True, context={"request": request}
                ).data,
                "nextCursor": page["nextCursor"],
                "hasMore": page["hasMore"],
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자 소유의 UUID 대화방을 생성합니다.

        예시 요청:
            POST /api/v1/assistant/conversations {"name": "새 대화"}

        요청/응답 계약:
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
            AssistantConversationSerializer(
                conversation, context={"request": request}
            ).data,
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
        return JsonResponse(
            AssistantConversationSerializer(
                conversation, context={"request": request}
            ).data
        )

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

        요청/응답 계약:
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

        요청/응답 계약:
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
        messages = [
            message
            for message in messages
            if not _message_access_denied(request=request, message=message)
        ]
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
            AssistantConversationSerializer(
                titled_conversation, context={"request": request}
            ).data,
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
            {"contextKey": "assistant:openwebui:portal"}

        요청 계약:
            contextKey만 지원하고 요약 갱신 metadata를 camelCase로 반환합니다.
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
        try:
            result = refresh_authorized_assistant_conversation_summary(
                user=request.user,
                request=request,
                conversation=conversation,
                context_key=context_key,
            )
        except AssistantConfigError as exc:
            logger.warning("Assistant 장기 요약 설정이 누락되었습니다.", exc_info=exc)
            return JsonResponse({"error": str(exc)}, status=503)
        except AssistantRequestError as exc:
            logger.warning("Assistant 장기 요약 생성에 실패했습니다.", exc_info=exc)
            return JsonResponse({"error": str(exc)}, status=502)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantConversationMessageView(APIView):
    """현재 사용자 대화방의 메시지 조회와 전체 삭제를 제공합니다."""

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

        요청/응답 계약:
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
                "results": AssistantMessageSerializer(
                    page["results"], many=True, context={"request": request}
                ).data,
                "nextCursor": page["nextCursor"],
                "hasMore": page["hasMore"],
            }
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

        요청/응답 계약:
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
        if _message_access_denied(request=request, message=message):
            return JsonResponse({"error": "permission_denied"}, status=403)
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
        if _message_access_denied(request=request, message=message):
            return JsonResponse({"error": "permission_denied"}, status=403)
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
        locked_message_ids = {
            message.id
            for message in messages
            if _message_access_denied(request=request, message=message)
        }
        conversation_payload = AssistantConversationSerializer(
            conversation,
            context={"request": request},
        ).data
        export_title = str(conversation_payload["name"])
        export_format = serializer.validated_data["format"]
        if export_format == "csv":
            content = build_assistant_csv_export(
                conversation=conversation,
                messages=messages,
                locked_message_ids=locked_message_ids,
                export_title=export_title,
            )
            extension = "csv"
            content_type = "text/csv; charset=utf-8"
        else:
            content = build_assistant_markdown_export(
                conversation=conversation,
                messages=messages,
                locked_message_ids=locked_message_ids,
                export_title=export_title,
            )
            extension = "md"
            content_type = "text/markdown; charset=utf-8"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="assistant-{conversation.id}.{extension}"'
        )
        return response
