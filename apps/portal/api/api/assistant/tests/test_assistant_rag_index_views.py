from . import *  # noqa: F403


class AssistantRagIndexViewsTests(TestCase):
    """RAG 인덱스/권한 그룹 API 동작을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/권한 데이터를 준비합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            email="s90000@example.com",
        )
        self.user.knox_id = "knox-90000"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")
        self.conversation = AssistantConversation.objects.create(
            user=self.user,
            title="RAG 테스트",
        )

        manager = User.objects.create_user(sabun="S90010", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        authority = User.objects.create_superuser(
            sabun="S90012",
            password="test-password",
        )
        affiliation = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-b",
        )
        payload, data_scope_status = account_services.update_user_scope_affiliation_data(
            actor=authority,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode="default",
            affiliation_ids=[affiliation.id],
            reason="Assistant 테스트 추가 범위",
        )
        self.assertEqual(data_scope_status, 200, payload)

    def test_rag_index_list_returns_accessible_user_sdwt_prods(self) -> None:
        """접근 가능한 user_sdwt_prod가 응답에 포함되는지 확인합니다."""
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-a")
        self.assertEqual(
            set(payload.get("permissionGroups", [])),
            {"group-a", "group-b", "knox-90000", rag_services.RAG_PUBLIC_GROUP},
        )
        self.assertEqual(payload.get("ragIndexes"), rag_services.get_rag_index_candidates())
        self.assertEqual(payload.get("defaultRagIndex"), rag_services.resolve_rag_index_name(None))
        self.assertEqual(
            payload.get("emailRagIndex"),
            rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        )

    def test_rag_index_list_returns_all_known_user_sdwt_prods_for_superuser(self) -> None:
        """슈퍼유저는 모든 user_sdwt_prod가 노출되는지 확인합니다."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["knox_id"])
        _set_current_affiliation(superuser, user_sdwt_prod="group-admin")

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        _set_current_affiliation(other_user, user_sdwt_prod="group-c")
        manager = User.objects.create_user(sabun="S90011", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-d")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-d",
            target_user=other_user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)

        self.client.force_login(superuser)
        conversation = AssistantConversation.objects.create(
            user=superuser,
            title="슈퍼유저 RAG 테스트",
        )

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-admin")
        permission_groups = payload.get("permissionGroups")
        self.assertEqual(permission_groups, sorted(permission_groups))
        self.assertEqual(
            set(permission_groups),
            {
                "group-a",
                "group-b",
                "group-c",
                "group-d",
                "group-admin",
                "knox-super",
                rag_services.RAG_PUBLIC_GROUP,
            },
        )
