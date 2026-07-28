import re

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ACCESS_MANAGERS_GROUP_NAME = "Access Managers"
MANAGE_ACCESS_CODENAME = "manage_access"
POLICY_AUDIT_ACTIONS = {"policy_create", "policy_update", "policy_delete"}
SCOPE_AUDIT_ACTIONS = {"scope_create", "scope_update", "scope_delete"}
ACCESS_SCOPE_KEY_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
AUDIT_LOG_BATCH_SIZE = 1000


def normalize_access_roles(apps, _schema_editor):
    """기존 접근 상태를 유지하면서 모든 역할을 일반 사용자로 정규화합니다."""

    UserAccess = apps.get_model("account", "UserAccess")

    UserAccess.objects.exclude(role="user").update(role="user")


def restore_legacy_roles(apps, _schema_editor):
    """역방향 migration에서 일반 역할을 기존 기본 역할인 `viewer`로 되돌립니다."""

    UserAccess = apps.get_model("account", "UserAccess")

    UserAccess.objects.filter(role="user").update(role="viewer")


def remove_legacy_access_manager_permission(apps, _schema_editor):
    """더 이상 권한 근거로 사용하지 않는 Django 그룹과 permission을 제거합니다."""

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    Group.objects.filter(name=ACCESS_MANAGERS_GROUP_NAME).delete()
    Permission.objects.filter(
        content_type__app_label="account",
        codename=MANAGE_ACCESS_CODENAME,
    ).delete()


def restore_legacy_access_manager_group(apps, _schema_editor):
    """역방향 migration에서 기존 권한 관리자 그룹과 permission을 복구합니다."""

    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type = ContentType.objects.get(app_label="account", model="user")
    permission, _created = Permission.objects.get_or_create(
        content_type=content_type,
        codename=MANAGE_ACCESS_CODENAME,
        defaults={"name": "포털 및 앱 접근 권한 관리"},
    )
    group, _created = Group.objects.get_or_create(name=ACCESS_MANAGERS_GROUP_NAME)
    group.permissions.add(permission)


def normalize_legacy_access_manager_audits(apps, _schema_editor):
    """기존 감사 action과 JSON snapshot 중 변경 대상만 묶어서 정규화합니다."""

    AccessAuditLog = apps.get_model("account", "AccessAuditLog")
    AccessScope = apps.get_model("account", "AccessScope")
    portal_scope = AccessScope.objects.filter(key="portal").first()
    changed_logs = []

    for audit_log in AccessAuditLog.objects.all().only(
        "id",
        "action",
        "before",
        "after",
        "scope",
    ).iterator(chunk_size=AUDIT_LOG_BATCH_SIZE):
        original_values = (
            audit_log.action,
            audit_log.before,
            audit_log.after,
            audit_log.scope_id,
        )
        if audit_log.action == "access_manager_grant":
            audit_log.action = "grant"
            audit_log.before = {}
            audit_log.after = {"explicitStatus": "allowed", "role": "admin"}
            audit_log.scope_id = getattr(portal_scope, "id", None)
        elif audit_log.action == "access_manager_revoke":
            audit_log.action = "change_role"
            audit_log.before = {"explicitStatus": "allowed", "role": "admin"}
            audit_log.after = {"explicitStatus": "allowed", "role": "user"}
            audit_log.scope_id = getattr(portal_scope, "id", None)

        audit_log.before = _canonicalize_audit_snapshot(
            action=audit_log.action,
            snapshot=audit_log.before,
        )
        audit_log.after = _canonicalize_audit_snapshot(
            action=audit_log.action,
            snapshot=audit_log.after,
        )
        normalized_values = (
            audit_log.action,
            audit_log.before,
            audit_log.after,
            audit_log.scope_id,
        )
        if normalized_values == original_values:
            continue

        changed_logs.append(audit_log)
        if len(changed_logs) >= AUDIT_LOG_BATCH_SIZE:
            AccessAuditLog.objects.bulk_update(
                changed_logs,
                ["action", "before", "after", "scope"],
                batch_size=AUDIT_LOG_BATCH_SIZE,
            )
            changed_logs.clear()

    if changed_logs:
        AccessAuditLog.objects.bulk_update(
            changed_logs,
            ["action", "before", "after", "scope"],
            batch_size=AUDIT_LOG_BATCH_SIZE,
        )


def _canonicalize_audit_snapshot(*, action, snapshot):
    """migration 시점의 과거 감사 snapshot을 action별 고정 필드로 제한합니다."""

    if not isinstance(snapshot, dict):
        return {}
    if action in POLICY_AUDIT_ACTIONS:
        return {
            key: snapshot.get(key)
            for key in ("id", "ruleType", "value", "isActive")
            if key in snapshot
        }
    if action in SCOPE_AUDIT_ACTIONS:
        return {
            key: snapshot.get(key)
            for key in ("key", "name", "scopeType", "isActive", "requestable")
            if key in snapshot
        }
    explicit_status = snapshot.get("explicitStatus", snapshot.get("status"))
    payload = {}
    if explicit_status in {"pending", "allowed", "denied"}:
        payload["explicitStatus"] = explicit_status
    role = snapshot.get("role")
    if isinstance(role, str):
        payload["role"] = "admin" if role.strip().lower() == "admin" else "user"
    return payload


def validate_access_scope_identity(apps, _schema_editor):
    """새 제약조건 적용 전에 의미를 자동 변경할 수 없는 scope를 명시적으로 보고합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    invalid_scopes = []
    for scope in AccessScope.objects.order_by("id").only("id", "key", "scope_type"):
        has_canonical_portal_identity = (
            scope.key == "portal" and scope.scope_type == "portal"
        ) or (
            scope.key != "portal" and scope.scope_type != "portal"
        )
        has_valid_key = bool(re.fullmatch(ACCESS_SCOPE_KEY_PATTERN, scope.key or ""))
        if has_canonical_portal_identity and has_valid_key:
            continue
        invalid_scopes.append(
            f"id={scope.id}, key={scope.key!r}, scope_type={scope.scope_type!r}"
        )

    if invalid_scopes:
        details = "; ".join(invalid_scopes[:20])
        raise RuntimeError(
            "AccessScope 식별자 정리가 필요합니다. migration 적용 전에 다음 행을 수정하세요: "
            f"{details}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0004_app_scope_requests"),
    ]

    operations = [
        migrations.RunPython(
            normalize_legacy_access_manager_audits,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="accessscope",
            name="chk_acc_scp_role_valid",
        ),
        migrations.RemoveConstraint(
            model_name="accesspolicyrule",
            name="chk_acc_pol_role_valid",
        ),
        migrations.RemoveConstraint(
            model_name="useraccess",
            name="chk_acc_usr_acc_role_valid",
        ),
        migrations.RunPython(
            normalize_access_roles,
            restore_legacy_roles,
        ),
        migrations.AlterModelOptions(
            name="user",
            options={},
        ),
        migrations.RemoveField(
            model_name="accessscope",
            name="default_role",
        ),
        migrations.RemoveField(
            model_name="accesspolicyrule",
            name="role",
        ),
        migrations.DeleteModel(
            name="UserProfile",
        ),
        migrations.AlterField(
            model_name="useraccess",
            name="role",
            field=models.CharField(
                choices=[("user", "User"), ("admin", "Admin")],
                default="user",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="accessauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("request", "Request"),
                    ("approve", "Approve"),
                    ("reject", "Reject"),
                    ("grant", "Grant"),
                    ("revoke", "Revoke"),
                    ("reset_to_policy", "Reset to policy"),
                    ("change_role", "Change role"),
                    ("policy_create", "Policy create"),
                    ("policy_update", "Policy update"),
                    ("policy_delete", "Policy delete"),
                    ("scope_create", "Scope create"),
                    ("scope_update", "Scope update"),
                    ("scope_delete", "Scope delete"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name="useraccess",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=("user", "admin")),
                name="chk_acc_usr_acc_role_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="useraccess",
            constraint=models.CheckConstraint(
                condition=models.Q(status="allowed") | models.Q(role="user"),
                name="chk_acc_usr_acc_role_state",
            ),
        ),
        migrations.RunPython(
            remove_legacy_access_manager_permission,
            restore_legacy_access_manager_group,
        ),
        migrations.RunPython(
            validate_access_scope_identity,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="accessscope",
            name="key",
            field=models.CharField(
                max_length=64,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="scope key는 소문자 영숫자와 하이픈만 사용할 수 있습니다.",
                        regex=ACCESS_SCOPE_KEY_PATTERN,
                    )
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="accessscope",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("key", "portal"), ("scope_type", "portal"))
                    | (
                        ~models.Q(("key", "portal"))
                        & ~models.Q(("scope_type", "portal"))
                    )
                ),
                name="chk_acc_scp_portal_key_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="accessscope",
            constraint=models.CheckConstraint(
                condition=models.Q(("key__regex", ACCESS_SCOPE_KEY_PATTERN)),
                name="chk_acc_scp_key_fmt",
            ),
        ),
        migrations.AlterField(
            model_name="accessauditlog",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_audit_actions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="accessauditlog",
            name="scope",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_logs",
                to="account.accessscope",
            ),
        ),
        migrations.AlterField(
            model_name="accessauditlog",
            name="target_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_audit_targets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
