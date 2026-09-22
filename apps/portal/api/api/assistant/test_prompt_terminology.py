"""Assistant 출력 경로의 영문 업무 용어 prompt 계약을 검증합니다."""

from unittest.mock import Mock

from django.test import SimpleTestCase

from api.assistant.services import (
    AssistantChatConfig,
    AssistantChatService,
    AssistantOpenWebUIConfig,
    build_openwebui_messages,
    request_openwebui_conversation_summary,
    request_openwebui_conversation_title,
)


class AssistantTerminologyPromptTests(SimpleTestCase):
    """일반·Email RAG·제목·요약 prompt가 공통 용어 guide를 사용하는지 확인합니다."""

    def assert_terminology_guide(self, prompt: str) -> None:
        """canonical 용어와 금지 음역 표기가 prompt에 함께 있는지 확인합니다."""

        for expected in (
            "[영문 업무 용어 보존 규칙]",
            "- interlock",
            "- wafer lot",
            "- production wafer",
            "인터록, 인터락",
            "웨이퍼 로트",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, prompt)

    def test_chat_and_email_rag_prompts_include_terminology_guide(self) -> None:
        """일반 대화와 Email RAG 구조화 제약에 같은 guide를 포함합니다."""

        general_prompt = build_openwebui_messages([])[0]["content"]
        email_payload = AssistantChatService(
            config=AssistantChatConfig(use_dummy=False)
        )._generate_llm_payload("wafer lot 질문", ["메일 근거"], email_ids=["E1"])
        email_prompt = email_payload["messages"][2]["content"]

        self.assert_terminology_guide(general_prompt)
        self.assert_terminology_guide(email_prompt)

    def test_title_and_summary_requests_include_terminology_guide(self) -> None:
        """자동 제목과 장기 요약 요청의 system prompt에도 guide를 전달합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "interlock과 wafer lot 분석"}}]
        }
        config = AssistantOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
        )
        title_session = Mock()
        title_session.post.return_value = response
        summary_session = Mock()
        summary_session.post.return_value = response

        request_openwebui_conversation_title(
            history=[{"role": "user", "content": "wafer lot을 분석해줘"}],
            config=config,
            session=title_session,
        )
        request_openwebui_conversation_summary(
            messages=[{"role": "assistant", "content": "interlock을 확인했습니다."}],
            config=config,
            session=summary_session,
        )

        self.assert_terminology_guide(
            title_session.post.call_args.kwargs["json"]["messages"][0]["content"]
        )
        self.assert_terminology_guide(
            summary_session.post.call_args.kwargs["json"]["messages"][0]["content"]
        )
