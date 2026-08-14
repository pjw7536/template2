"""Work Hub Django 앱 설정입니다."""

from django.apps import AppConfig


class WorkHubConfig(AppConfig):
    """Work Hub 도메인 앱을 등록합니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.work_hub"

    def ready(self) -> None:
        """Portal account 변경을 Work Hub 접근 동기화 Outbox에 연결합니다."""

        from django.apps import apps
        from django.contrib.auth import get_user_model

        from .services.access_events import register_access_sync_signals

        register_access_sync_signals(
            user_model=get_user_model(),
            affiliation_model=apps.get_model("account", "Affiliation"),
            current_affiliation_model=apps.get_model(
                "account", "UserCurrentAffiliation"
            ),
            access_model=apps.get_model("account", "UserSdwtProdAccess"),
            user_access_model=apps.get_model("account", "UserAccess"),
            scope_affiliation_grant_model=apps.get_model(
                "account", "UserScopeAffiliationGrant"
            ),
            access_policy_model=apps.get_model("account", "AccessPolicyRule"),
            access_scope_model=apps.get_model("account", "AccessScope"),
        )
