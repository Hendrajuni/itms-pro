from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0024_location_parent_location_type'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE assets_location DROP COLUMN IF EXISTS location_type;",
            reverse_sql="ALTER TABLE assets_location ADD COLUMN location_type varchar(20);"
        ),
    ]
