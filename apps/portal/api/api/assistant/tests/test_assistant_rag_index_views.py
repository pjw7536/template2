from . import *  # noqa: F403


class AssistantRagIndexViewsTests(TestCase):
    """조직 목록 없이 세션 SDWT 권한을 RAG UI에 전달합니다."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(avatarid="RAG-EPID", sabun="RAG-SABUN", knox_id="rag.user")

    def test_rag_index_list_returns_granted_groups(self):
        _set_keycloak_access(self.user, roles=["assistant-user", "emails-user"],
            sdwt="A", groups=["/A/viewer", "/B/user"])
        _keycloak_login(self.client, self.user)
        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload["permissionGroups"]), {"A", "B", "rag.user", rag_services.RAG_PUBLIC_GROUP})
        self.assertEqual(payload["currentUserSdwtProd"], "A")
        self.assertFalse(payload["allPermissionGroups"])

    def test_portal_admin_reports_all_without_loading_catalog(self):
        _set_keycloak_access(self.user, roles=["portal-admin"])
        _keycloak_login(self.client, self.user)
        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["allPermissionGroups"])
        self.assertEqual(set(response.json()["permissionGroups"]), {"rag.user", rag_services.RAG_PUBLIC_GROUP})
