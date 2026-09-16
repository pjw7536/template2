"""Assistant exports API입니다."""

from ._shared import *  # noqa: F403


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
