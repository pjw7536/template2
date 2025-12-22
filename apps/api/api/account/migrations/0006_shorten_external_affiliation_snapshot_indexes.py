from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0005_remove_duplicate_user_fields"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="externalaffiliationsnapshot",
            old_name="idx_account_external_affiliation_snapshot_user_sdwt_prod",
            new_name="idx_ext_aff_snap_sdwt",
        ),
        migrations.RenameIndex(
            model_name="externalaffiliationsnapshot",
            old_name="idx_account_external_affiliation_snapshot_source_updated_at",
            new_name="idx_ext_aff_snap_src_upd",
        ),
    ]
