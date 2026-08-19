"""Assistant conversations API입니다."""

from ._shared import *  # noqa: F403


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
