from django.db import migrations


SET_CREATED_DEFAULT = """
ALTER TABLE drone_sop_v3
ALTER COLUMN created_at SET DEFAULT (timezone('utc', now()));
"""

SET_UPDATED_DEFAULT = """
ALTER TABLE drone_sop_v3
ALTER COLUMN updated_at SET DEFAULT (timezone('utc', now()));
"""

DROP_CREATED_DEFAULT = """
ALTER TABLE drone_sop_v3
ALTER COLUMN created_at DROP DEFAULT;
"""

DROP_UPDATED_DEFAULT = """
ALTER TABLE drone_sop_v3
ALTER COLUMN updated_at DROP DEFAULT;
"""

CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION set_drone_sop_v3_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

DROP_FUNCTION = """
DROP FUNCTION IF EXISTS set_drone_sop_v3_updated_at();
"""

CREATE_TRIGGER = """
DROP TRIGGER IF EXISTS drone_sop_v3_updated_at ON drone_sop_v3;
CREATE TRIGGER drone_sop_v3_updated_at
BEFORE UPDATE ON drone_sop_v3
FOR EACH ROW
EXECUTE FUNCTION set_drone_sop_v3_updated_at();
"""

DROP_TRIGGER = """
DROP TRIGGER IF EXISTS drone_sop_v3_updated_at ON drone_sop_v3;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0003_add_line_sdwt_index"),
    ]

    operations = [
        migrations.RunSQL(SET_CREATED_DEFAULT, DROP_CREATED_DEFAULT),
        migrations.RunSQL(SET_UPDATED_DEFAULT, DROP_UPDATED_DEFAULT),
        migrations.RunSQL(CREATE_FUNCTION, DROP_FUNCTION),
        migrations.RunSQL(CREATE_TRIGGER, DROP_TRIGGER),
    ]
