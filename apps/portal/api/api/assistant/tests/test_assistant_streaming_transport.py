from . import *  # noqa: F403


class AssistantStreamingTransportTests(SimpleTestCase):
    """OpenAI 호환 token stream과 사용자 중단 전파를 검증합니다."""

    def test_openai_stream_requests_real_stream_and_yields_each_delta(self) -> None:
        """transport가 stream=true를 보내고 도착한 content chunk를 즉시 반환합니다."""

        from api.common.services import stream_openai_chat_completion

        response = Mock()
        response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"첫"}}]}',
            'data: {"choices":[{"delta":{"content":" 번째"}}]}',
            "data: [DONE]",
        ]
        session = Mock()
        session.post.return_value = response
        cancellation = ExternalCallCancellation()

        deltas = list(
            stream_openai_chat_completion(
                url="http://llm/chat/completions",
                headers={"X-Test": "1"},
                payload={"model": "test", "messages": []},
                timeout_seconds=10,
                cancellation=cancellation,
                session=session,
            )
        )

        self.assertEqual(deltas, ["첫", " 번째"])
        request_kwargs = session.post.call_args.kwargs
        self.assertTrue(request_kwargs["stream"])
        self.assertTrue(request_kwargs["json"]["stream"])

    def test_stream_cancellation_closes_active_response(self) -> None:
        """브라우저 중단과 같은 cancellation은 열린 upstream response를 닫습니다."""

        from api.common.services import stream_openai_chat_completion

        response = Mock()
        response.iter_lines.return_value = iter(
            [
                'data: {"choices":[{"delta":{"content":"진행 중"}}]}',
                'data: {"choices":[{"delta":{"content":"늦은 응답"}}]}',
            ]
        )
        session = Mock()
        session.post.return_value = response
        cancellation = ExternalCallCancellation()
        stream = stream_openai_chat_completion(
            url="http://llm/chat/completions",
            headers={},
            payload={"model": "test", "messages": []},
            timeout_seconds=10,
            cancellation=cancellation,
            session=session,
        )

        self.assertEqual(next(stream), "진행 중")
        cancellation.cancel()
        with self.assertRaises(ExternalCallCancelled):
            next(stream)
        response.close.assert_called()

    def test_runtime_generator_close_cancels_worker(self) -> None:
        """SSE generator 종료가 worker의 cancellation token까지 전달됩니다."""

        from api.assistant.services.runtime_execution import (
            stream_assistant_runtime_execution,
        )

        cancelled = threading.Event()

        class BlockingRuntime:
            """첫 delta 이후 cancellation을 기다리는 테스트 Runtime입니다."""

            def execute(self, **kwargs):
                kwargs["on_delta"]("첫 토큰")
                token = kwargs["cancellation"]
                while not token.cancelled:
                    time.sleep(0.01)
                cancelled.set()
                token.raise_if_cancelled()

        execution = stream_assistant_runtime_execution(
            runtime=BlockingRuntime(),
            profile=assistant_services.get_assistant_profile(
                profile_key="portal-default"
            ),
            prompt="질문",
            history=[],
            conversation_summary="",
            tool_inputs={},
            user_header_id="knox-test",
            context_key="assistant:openwebui:portal",
        )
        first_event = next(execution)
        self.assertEqual(first_event.kind, "delta")

        execution.close()

        self.assertTrue(cancelled.wait(timeout=1))
