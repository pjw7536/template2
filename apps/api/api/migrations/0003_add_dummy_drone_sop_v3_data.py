from django.db import migrations


DUMMY_COMMENT = "Dummy data for testing"


def create_dummy_drone_sop_v3(apps, schema_editor):
    DroneSOPV3 = apps.get_model("api", "DroneSOPV3")

    dummy_entries = []
    for index in range(1, 1001):
        dummy_entries.append(
            DroneSOPV3(
                line_id=f"LINE{index % 20 + 1:02}",
                sdwt_prod=f"SDWT{index % 10 + 1:02}",
                sample_type=f"TYPE{index % 5 + 1:02}",
                sample_group=f"GROUP{index % 8 + 1:02}",
                eqp_id=f"EQP{index:04}",
                chamber_ids=f"CH{index % 5 + 1:02}",
                lot_id=f"LOT{index:05}",
                proc_id=f"PROC{index % 7 + 1:02}",
                ppid=f"PPID{index % 6 + 1:02}",
                main_step=f"STEP{index % 15 + 1:02}",
                metro_current_step=f"MSTEP{index % 9 + 1:02}",
                metro_steps=f"MSTEP{index % 9 + 1:02}->MSTEP{index % 9 + 2:02}",
                metro_end_step=f"MEND{index % 4 + 1:02}",
                status="OPEN" if index % 2 == 0 else "CLOSED",
                knoxid=f"KNOX{index % 11 + 1:02}",
                comment=DUMMY_COMMENT,
                user_sdwt_prod="abc",
                defect_url=f"https://example.com/defect/{index}",
                send_jira=False,
                needtosend=True,
                custom_end_step=f"CSTEP{index % 3 + 1:02}",
                inform_step=f"ISTEP{index % 5 + 1:02}",
                jira_key=None,
            )
        )

    DroneSOPV3.objects.bulk_create(dummy_entries, ignore_conflicts=True)


def delete_dummy_drone_sop_v3(apps, schema_editor):
    DroneSOPV3 = apps.get_model("api", "DroneSOPV3")
    DroneSOPV3.objects.filter(user_sdwt_prod="abc", comment=DUMMY_COMMENT).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0002_drone_tables"),
    ]

    operations = [
        migrations.RunPython(create_dummy_drone_sop_v3, delete_dummy_drone_sop_v3),
    ]
