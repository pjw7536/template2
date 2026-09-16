"""Assistant turns API입니다."""

from ._shared import *  # noqa: F403


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
