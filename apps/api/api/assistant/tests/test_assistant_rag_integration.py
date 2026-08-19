from . import *  # noqa: F403


class AssistantRagIntegrationTests(SimpleTestCase):
    """Assistant와 RAG 연동 경로를 검증합니다."""

    def test_generate_reply_uses_rag_services_search(self) -> None:
        """generate_reply가 RAG 검색을 호출하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답 더미 준비
        # -------------------------------------------------------------------------
        rag_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "doc_id": "email-1",
                            "title": "첫번째",
                            "merge_title_content": "컨텍스트1",
                        },
                    },
                    {
                        "_id": "doc-2",
                        "_source": {
                            "doc_id": "email-2",
                            "title": "두번째",
                            "merge_title_content": "컨텍스트2",
                        },
                    },
                ]
            }
        }

        # -------------------------------------------------------------------------
        # 2) Assistant 설정 구성
        # -------------------------------------------------------------------------
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["rp-unclassified"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 3) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.rag_adapter.search", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply_stream(
                "hello",
                cancellation=ExternalCallCancellation(),
            )

        # -------------------------------------------------------------------------
        # 4) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with(
            "hello",
            index_names=["rp-unclassified"],
            num_result_doc=5,
            timeout=30,
            cancellation=ANY,
        )
        self.assertTrue(result.is_dummy)
        self.assertEqual(
            result.contexts,
            [
                "[emailId: email-1 | title: 첫번째]\n컨텍스트1",
                "[emailId: email-2 | title: 두번째]\n컨텍스트2",
            ],
        )

    def test_generate_reply_passes_permission_group_override(self) -> None:
        """permission_groups 오버라이드가 전달되는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답/설정 준비
        # -------------------------------------------------------------------------
        rag_response = {"hits": {"hits": []}}
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["rp-unclassified"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 2) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.rag_adapter.search", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply_stream(
                "hello",
                permission_groups=["group-a"],
                cancellation=ExternalCallCancellation(),
            )

        # -------------------------------------------------------------------------
        # 3) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with(
            "hello",
            index_names=["rp-unclassified"],
            num_result_doc=5,
            timeout=30,
            permission_groups=["group-a"],
            cancellation=ANY,
        )
        self.assertEqual(result.sources, [])
        self.assertEqual(result.rag_response, rag_response)

    def test_rag_hit_with_mismatched_email_scope_is_removed_before_llm(self) -> None:
        """RAG가 잘못 반환한 다른 mailbox 문서는 LLM 배경지식에 포함하지 않습니다."""

        rag_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "forbidden-doc",
                        "_source": {
                            "doc_id": "email-forbidden",
                            "title": "보호 메일",
                            "merge_title_content": "노출되면 안 되는 본문",
                            "user_sdwt_prod": "group-b",
                            "permission_groups": ["group-b"],
                        },
                    }
                ]
            }
        }
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["rp-emails"],
        )
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.rag_adapter.search",
            return_value=rag_response,
        ):
            result = AssistantChatService(config=config).generate_reply_stream(
                "메일을 찾아줘",
                permission_groups=["group-a"],
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(result.contexts, [])
        self.assertEqual(result.sources, [])
