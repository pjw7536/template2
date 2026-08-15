# Django 5.2.16으로 2026-08-10에 생성했습니다.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


WORK_HUB_SCOPE_KEY = "work-hub"


def create_work_hub_access_scope(apps, schema_editor):
    """Work Hub 앱 접근 scope를 멱등하게 생성합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    database_alias = schema_editor.connection.alias
    scope, created = AccessScope.objects.using(database_alias).get_or_create(
        key=WORK_HUB_SCOPE_KEY,
        defaults={
            "name": "설비 업무일지",
            "scope_type": "app",
            "data_scope_type": "affiliation",
            "include_current_affiliation": True,
            "is_active": True,
            "requestable": True,
        },
    )
    if created:
        return
    if scope.scope_type != "app":
        raise RuntimeError("기존 work-hub scope의 scope_type이 app이 아닙니다.")
    AccessScope.objects.using(database_alias).filter(pk=scope.pk).update(
        name="설비 업무일지",
        data_scope_type="affiliation",
        include_current_affiliation=True,
        is_active=True,
        requestable=True,
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('account', '0006_account_authorization_system'),
    ]

    operations = [
        # 기존 scope 여부를 판별할 수 없으므로 역적용에서 접근·권한 데이터를 보존합니다.
        migrations.RunPython(
            create_work_hub_access_scope,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name='GristDocumentScope',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workspace_id', models.PositiveBigIntegerField()),
                ('doc_id', models.CharField(max_length=128)),
                ('equipment_table_id', models.CharField(default='Equipment', max_length=64)),
                ('worklog_table_id', models.CharField(default='WorkLog', max_length=64)),
                ('task_table_id', models.CharField(default='Task', max_length=64)),
                ('launch_url', models.URLField(max_length=500)),
                ('template_revision', models.CharField(default='grist-work-hub-v1', max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('affiliation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='grist_document_scopes', to='account.affiliation')),
            ],
            options={
                'db_table': 'work_hub_grist_document_scope',
            },
        ),
        migrations.CreateModel(
            name='GristAccessSyncOutbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(default='portal_access_changed', max_length=64)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed'), ('terminal', 'Terminal')], default='pending', max_length=16)),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('available_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('document_scope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_sync_outbox_items', to='work_hub.gristdocumentscope')),
            ],
            options={
                'db_table': 'work_hub_grist_access_sync_outbox',
            },
        ),
        migrations.CreateModel(
            name='GristTaskLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('worklog_row_id', models.PositiveBigIntegerField()),
                ('task_row_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('task_key', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_scope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_links', to='work_hub.gristdocumentscope')),
            ],
            options={
                'db_table': 'work_hub_grist_task_link',
            },
        ),
        migrations.CreateModel(
            name='GristWebhookReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=128, unique=True)),
                ('event_type', models.CharField(default='rows.changed', max_length=64)),
                ('doc_id', models.CharField(max_length=128)),
                ('table_id', models.CharField(max_length=64)),
                ('row_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('payload_hash', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('received', 'Received'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')], default='received', max_length=16)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'work_hub_grist_webhook_receipt',
                'indexes': [models.Index(fields=['status', 'processed_at'], name='idx_wrk_hub_hook_sts_prc'), models.Index(fields=['doc_id', 'table_id', 'row_id'], name='idx_wrk_hub_hook_doc_tbl_row')],
            },
        ),
        migrations.AddIndex(
            model_name='gristdocumentscope',
            index=models.Index(fields=['is_active'], name='idx_wrk_hub_doc_scp_act'),
        ),
        migrations.AddConstraint(
            model_name='gristdocumentscope',
            constraint=models.UniqueConstraint(fields=('affiliation',), name='uniq_wrk_hub_doc_scp_aff'),
        ),
        migrations.AddConstraint(
            model_name='gristdocumentscope',
            constraint=models.UniqueConstraint(fields=('doc_id',), name='uniq_wrk_hub_doc_scp_doc'),
        ),
        migrations.AddIndex(
            model_name='gristaccesssyncoutbox',
            index=models.Index(fields=['status', 'available_at'], name='idx_wrk_hub_gr_acc_sts'),
        ),
        migrations.AddIndex(
            model_name='gristaccesssyncoutbox',
            index=models.Index(fields=['document_scope', 'created_at'], name='idx_wrk_hub_gr_acc_scp'),
        ),
        migrations.AddIndex(
            model_name='gristtasklink',
            index=models.Index(fields=['worklog_row_id'], name='idx_wrk_hub_task_wrk'),
        ),
        migrations.AddConstraint(
            model_name='gristtasklink',
            constraint=models.UniqueConstraint(fields=('document_scope', 'worklog_row_id'), name='uniq_wrk_hub_task_scp_wrk'),
        ),
    ]
