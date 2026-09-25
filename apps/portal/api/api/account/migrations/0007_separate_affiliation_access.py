"""소속에서 파생된 권한을 명시적 권한으로 보존하고 자동 연결을 해제합니다."""

from django.db import migrations
from django.db.models.functions import Lower, Trim


def preserve_access(apps, schema_editor):
    """기존 역할·데이터 범위와 소속 부서 fallback 접근을 보존합니다."""

    database = schema_editor.connection.alias
    Current = apps.get_model("account", "UserCurrentAffiliation")
    Role = apps.get_model("account", "UserSdwtProdAccess")
    Grant = apps.get_model("account", "UserScopeAffiliationGrant")
    Scope = apps.get_model("account", "AccessScope")
    Policy = apps.get_model("account", "AccessPolicyRule")
    Access = apps.get_model("account", "UserAccess")
    reason = "등록 소속과 접근 권한 분리 시 기존 접근 보존"
    scope_ids = list(Scope.objects.using(database).filter(
        include_current_affiliation=True, data_scope_type="affiliation",
    ).values_list("id", flat=True))

    for current in Current.objects.using(database).filter(
        affiliation__is_active=True,
    ).select_related("user", "affiliation").iterator():
        role, _ = Role.objects.using(database).get_or_create(
            user_id=current.user_id, affiliation_id=current.affiliation_id,
            defaults={"role": "member"},
        )
        if role.role == "viewer":
            role.role = "member"
            role.save(using=database, update_fields=["role"])
        for scope_id in scope_ids:
            # 현재 소속은 기존의 만료·비활성 명시 grant와 무관하게 포함됐습니다.
            grant, created = Grant.objects.using(database).get_or_create(
                user_id=current.user_id, scope_id=scope_id,
                affiliation_id=current.affiliation_id,
                defaults={"source": "manual", "reason": reason},
            )
            if not created and (not grant.is_active or grant.expires_at is not None):
                grant.is_active = True
                grant.expires_at = None
                grant.reason = reason
                grant.source = "manual"
                grant.save(using=database, update_fields=["is_active", "expires_at", "reason", "source"])

        # 사용자 identity 부서가 없을 때 소속 부서로 허용되던 정책만 이관합니다.
        if not (current.user.department or "").strip():
            department = current.affiliation.department.strip()
            normalized = Current.objects.using(database).filter(pk=current.pk).annotate(
                normalized=Lower(Trim("affiliation__department")),
            ).values_list("normalized", flat=True).get()
            policies = Policy.objects.using(database).filter(is_active=True).annotate(
                normalized=Lower(Trim("value")),
            ).filter(normalized=normalized)
            for scope_id in policies.values_list("scope_id", flat=True).distinct():
                # 거절·대기·기존 명시 권한은 변경하지 않습니다.
                Access.objects.using(database).get_or_create(
                    user_id=current.user_id, scope_id=scope_id,
                    defaults={"status": "allowed", "role": "user",
                              "department": department, "reason": reason},
                )
    Scope.objects.using(database).update(include_current_affiliation=False)
    Current.objects.using(database).update(requires_reconfirm=False)


class Migration(migrations.Migration):
    dependencies = [("account", "0006_account_authorization_system")]
    operations = [
        migrations.RunPython(preserve_access, migrations.RunPython.noop),
    ]
