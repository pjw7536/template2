"""Assistant messages API입니다."""

from ._shared import *  # noqa: F403


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
