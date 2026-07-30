import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Coalesce, Lower, Trim


AFFILIATION_SCOPE_KEYS = ("assistant", "emails")
MIGRATION_BATCH_SIZE = 1000
VALID_AFFILIATION_ROLES = ("viewer", "member", "manager")
VALID_AFFILIATION_CHANGE_STATUSES = (
    "PENDING",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
)


def validate_affiliation_access_integrity(apps, schema_editor):
    """제약 추가 전에 중복 소속과 잘못된 역할 데이터를 차단합니다."""

    Affiliation = apps.get_model("account", "Affiliation")
    UserSdwtProdAccess = apps.get_model("account", "UserSdwtProdAccess")
    UserSdwtProdChange = apps.get_model("account", "UserSdwtProdChange")
    database_alias = schema_editor.connection.alias

    seen_values = {}
    duplicate_pairs = []
    blank_ids = []
    whitespace_ids = []
    affiliations = (
        Affiliation.objects.using(database_alias)
        .annotate(_lookup_value=Lower(Trim("user_sdwt_prod")))
        .order_by("id")
    )
    for affiliation in affiliations:
        normalized = (affiliation.user_sdwt_prod or "").strip()
        if not normalized:
            blank_ids.append(affiliation.id)
            continue
        if affiliation.user_sdwt_prod != normalized:
            whitespace_ids.append(affiliation.id)
        lookup_value = affiliation._lookup_value
        previous_id = seen_values.get(lookup_value)
        if previous_id is not None:
            duplicate_pairs.append((previous_id, affiliation.id))
        else:
            seen_values[lookup_value] = affiliation.id

    invalid_role_ids = list(
        UserSdwtProdAccess.objects.using(database_alias)
        .exclude(role__in=VALID_AFFILIATION_ROLES)
        .order_by("id")
        .values_list("id", flat=True)[:20]
    )
    findings = []
    if blank_ids:
        findings.append(f"빈 소속 식별자 id={blank_ids[:20]}")
    if whitespace_ids:
        findings.append(f"앞뒤 공백이 있는 소속 식별자 id={whitespace_ids[:20]}")
    if duplicate_pairs:
        findings.append(f"대소문자·공백 기준 중복 소속 id 쌍={duplicate_pairs[:20]}")
    if invalid_role_ids:
        findings.append(f"잘못된 소속 접근 역할 id={invalid_role_ids}")
    invalid_change_status_ids = list(
        UserSdwtProdChange.objects.using(database_alias)
        .exclude(status__in=VALID_AFFILIATION_CHANGE_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)[:20]
    )
    if invalid_change_status_ids:
        findings.append(f"잘못된 소속 변경 상태 id={invalid_change_status_ids}")
    if findings:
        raise RuntimeError(
            "소속 접근 무결성 제약을 적용할 수 없습니다. "
            + "; ".join(findings)
        )


def seed_app_affiliation_data_scopes(apps, schema_editor):
    """앱별 소속 범위 정책을 설정하고 기존 전역 소속 grant를 안전하게 복제합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    UserAccess = apps.get_model("account", "UserAccess")
    UserSdwtProdAccess = apps.get_model("account", "UserSdwtProdAccess")
    UserScopeAffiliationGrant = apps.get_model(
        "account",
        "UserScopeAffiliationGrant",
    )
    database_alias = schema_editor.connection.alias

    scopes = {
        scope.key: scope
        for scope in AccessScope.objects.using(database_alias).filter(
            key__in=AFFILIATION_SCOPE_KEYS,
        )
    }
    missing_keys = sorted(set(AFFILIATION_SCOPE_KEYS) - set(scopes))
    if missing_keys:
        raise RuntimeError(
            "앱별 소속 범위를 설정할 AccessScope가 없습니다: "
            + ", ".join(missing_keys)
        )

    AccessScope.objects.using(database_alias).filter(
        key__in=AFFILIATION_SCOPE_KEYS,
    ).update(
        data_scope_type="affiliation",
        include_current_affiliation=True,
    )

    legacy_rows = (
        UserSdwtProdAccess.objects.using(database_alias)
        .order_by("id")
        .values("user_id", "affiliation_id", "granted_by_id")
        .iterator(chunk_size=MIGRATION_BATCH_SIZE)
    )
    ordered_scopes = [
        scopes[scope_key]
        for scope_key in AFFILIATION_SCOPE_KEYS
    ]
    grants = []
    for row in legacy_rows:
        for scope in ordered_scopes:
            grants.append(
                UserScopeAffiliationGrant(
                    user_id=row["user_id"],
                    scope_id=scope.id,
                    affiliation_id=row["affiliation_id"],
                    source="manual",
                    is_active=True,
                    granted_by_id=row["granted_by_id"],
                    reason="기존 전역 소속 접근 권한에서 앱별 데이터 범위로 전환",
                )
            )
        if len(grants) < MIGRATION_BATCH_SIZE:
            continue
        UserScopeAffiliationGrant.objects.using(database_alias).bulk_create(
            grants,
            ignore_conflicts=True,
            batch_size=MIGRATION_BATCH_SIZE,
        )
        grants = []
    if grants:
        UserScopeAffiliationGrant.objects.using(database_alias).bulk_create(
            grants,
            ignore_conflicts=True,
            batch_size=MIGRATION_BATCH_SIZE,
        )

    UserAccess.objects.using(database_alias).filter(
        scope_id=scopes["emails"].id,
        status="allowed",
        role="admin",
    ).update(data_scope_mode="all")


def reset_app_affiliation_data_scopes(apps, schema_editor):
    """역방향 migration에서 앱 데이터 범위 설정을 기본값으로 되돌립니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    UserAccess = apps.get_model("account", "UserAccess")
    database_alias = schema_editor.connection.alias

    AccessScope.objects.using(database_alias).filter(
        key__in=AFFILIATION_SCOPE_KEYS,
    ).update(
        data_scope_type="none",
        include_current_affiliation=False,
    )
    UserAccess.objects.using(database_alias).filter(
        scope__key__in=AFFILIATION_SCOPE_KEYS,
    ).update(data_scope_mode="default")


def supersede_duplicate_pending_affiliation_changes(apps, schema_editor):
    """사용자별 최신 한 건을 제외한 중복 대기 소속 요청을 대체 상태로 정리합니다."""

    UserSdwtProdChange = apps.get_model("account", "UserSdwtProdChange")
    database_alias = schema_editor.connection.alias
    duplicate_user_ids = (
        UserSdwtProdChange.objects.using(database_alias)
        .filter(status="PENDING")
        .values("user_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .values_list("user_id", flat=True)
        .iterator(chunk_size=MIGRATION_BATCH_SIZE)
    )

    for user_id in duplicate_user_ids:
        pending_ids = list(
            UserSdwtProdChange.objects.using(database_alias)
            .filter(user_id=user_id, status="PENDING")
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)
        )
        UserSdwtProdChange.objects.using(database_alias).filter(
            id__in=pending_ids[1:],
        ).update(
            status="SUPERSEDED",
            approved=False,
            approved_by_id=None,
            approved_at=None,
            applied=False,
            rejection_reason="취소(중복 대기 요청 정리)",
        )


def normalize_affiliation_change_states(apps, schema_editor):
    """소속 변경 상태별 승인 메타데이터를 단일 상태 규칙에 맞춥니다."""

    UserSdwtProdChange = apps.get_model("account", "UserSdwtProdChange")
    database_alias = schema_editor.connection.alias
    UserSdwtProdChange.objects.using(database_alias).filter(
        status="PENDING",
    ).update(
        approved=False,
        applied=False,
        approved_by_id=None,
        approved_at=None,
        rejection_reason=None,
    )
    UserSdwtProdChange.objects.using(database_alias).filter(
        status="APPROVED",
    ).update(
        approved=True,
        applied=True,
        approved_at=Coalesce("approved_at", "created_at"),
        rejection_reason=None,
    )
    UserSdwtProdChange.objects.using(database_alias).filter(
        status="REJECTED",
    ).update(
        approved=False,
        applied=False,
        approved_at=Coalesce("approved_at", "created_at"),
    )
    UserSdwtProdChange.objects.using(database_alias).filter(
        status="SUPERSEDED",
    ).update(
        approved=False,
        applied=False,
        approved_by_id=None,
        approved_at=None,
    )
    # 같은 atomic migration에서 이어지는 partial unique index 생성 전에
    # PostgreSQL의 지연 FK trigger를 확정해 DDL 충돌을 방지합니다.
    schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0005_fixed_access_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            validate_affiliation_access_integrity,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="affiliation",
            name="uniq_acc_aff_usr_sdw_prd",
        ),
        migrations.AddConstraint(
            model_name="affiliation",
            constraint=models.UniqueConstraint(
                Lower(Trim("user_sdwt_prod")),
                name="uniq_acc_aff_usr_sdw_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="usersdwtprodaccess",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=VALID_AFFILIATION_ROLES),
                name="chk_acc_usr_sdw_acs_role",
            ),
        ),
        migrations.AddField(
            model_name="affiliation",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="accessscope",
            name="data_scope_type",
            field=models.CharField(
                choices=[("none", "None"), ("affiliation", "Affiliation")],
                default="none",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="accessscope",
            name="include_current_affiliation",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="useraccess",
            name="data_scope_mode",
            field=models.CharField(
                choices=[("default", "Default"), ("all", "All")],
                default="default",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="accessauditlog",
            name="affiliation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_audit_logs",
                to="account.affiliation",
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
                    ("data_scope_grant", "Data scope grant"),
                    ("data_scope_revoke", "Data scope revoke"),
                    ("data_scope_change", "Data scope change"),
                    ("affiliation_role_grant", "Affiliation role grant"),
                    ("affiliation_role_change", "Affiliation role change"),
                    ("affiliation_role_revoke", "Affiliation role revoke"),
                    ("affiliation_create", "Affiliation create"),
                    ("affiliation_update", "Affiliation update"),
                    ("affiliation_activate", "Affiliation activate"),
                    ("affiliation_deactivate", "Affiliation deactivate"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="UserScopeAffiliationGrant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("policy", "Policy"),
                            ("external", "External"),
                        ],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "affiliation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scope_user_grants",
                        to="account.affiliation",
                    ),
                ),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="scope_affiliation_grants_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "scope",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="affiliation_grants",
                        to="account.accessscope",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scope_affiliation_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "account_user_scope_aff_grant",
                "indexes": [
                    models.Index(
                        fields=["user", "scope", "is_active"],
                        name="idx_acc_usr_scp_aff_act",
                    ),
                    models.Index(
                        fields=["scope", "affiliation", "is_active"],
                        name="idx_acc_scp_aff_grt_act",
                    ),
                    models.Index(
                        fields=["expires_at"],
                        name="idx_acc_scp_aff_exp",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "scope", "affiliation"),
                        name="uniq_acc_usr_scp_aff_grt",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            source__in=("manual", "policy", "external"),
                        ),
                        name="chk_acc_usr_scp_aff_src",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="affiliation",
            index=models.Index(
                fields=["is_active"],
                name="idx_acc_aff_act",
            ),
        ),
        migrations.AddIndex(
            model_name="accessauditlog",
            index=models.Index(
                fields=["affiliation", "created_at"],
                name="idx_acc_aud_aff_ct",
            ),
        ),
        migrations.AddConstraint(
            model_name="accessscope",
            constraint=models.CheckConstraint(
                condition=models.Q(data_scope_type__in=("none", "affiliation")),
                name="chk_acc_scp_dat_typ_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="accessscope",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(data_scope_type="affiliation")
                    | models.Q(include_current_affiliation=False)
                ),
                name="chk_acc_scp_cur_aff_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="accessscope",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(scope_type="portal")
                    | models.Q(
                        data_scope_type="none",
                        include_current_affiliation=False,
                    )
                ),
                name="chk_acc_scp_portal_no_data",
            ),
        ),
        migrations.AddConstraint(
            model_name="useraccess",
            constraint=models.CheckConstraint(
                condition=models.Q(data_scope_mode__in=("default", "all")),
                name="chk_acc_usr_acc_dat_mode",
            ),
        ),
        migrations.AddConstraint(
            model_name="useraccess",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(status="allowed")
                    | models.Q(data_scope_mode="default")
                ),
                name="chk_acc_usr_acc_dat_state",
            ),
        ),
        migrations.RunPython(
            seed_app_affiliation_data_scopes,
            reset_app_affiliation_data_scopes,
        ),
        migrations.AddConstraint(
            model_name="affiliation",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(user_sdwt_prod="")
                    & models.Q(
                        user_sdwt_prod=Trim(models.F("user_sdwt_prod")),
                    )
                ),
                name="chk_acc_aff_usr_sdw_trim",
            ),
        ),
        migrations.RunPython(
            supersede_duplicate_pending_affiliation_changes,
            migrations.RunPython.noop,
        ),
        migrations.RunPython(
            normalize_affiliation_change_states,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="usersdwtprodchange",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="PENDING"),
                fields=("user",),
                name="uniq_acc_usr_sdw_chg_pend",
            ),
        ),
        migrations.AddConstraint(
            model_name="usersdwtprodchange",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="APPROVED",
                        approved=True,
                        applied=True,
                        approved_at__isnull=False,
                        rejection_reason__isnull=True,
                    )
                    | models.Q(
                        status="PENDING",
                        approved=False,
                        applied=False,
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                        rejection_reason__isnull=True,
                    )
                    | models.Q(
                        status="REJECTED",
                        approved=False,
                        applied=False,
                        approved_at__isnull=False,
                    )
                    | models.Q(
                        status="SUPERSEDED",
                        approved=False,
                        applied=False,
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                ),
                name="chk_acc_usr_sdw_chg_state",
            ),
        ),
    ]
