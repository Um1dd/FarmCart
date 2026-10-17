from django.db import migrations


def initialize(apps, schema_editor):
    apps.get_model("shop", "OwnerState").objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("shop", "0004_securitythrottle_adminchallenge_and_more")]
    operations = [migrations.RunPython(initialize, migrations.RunPython.noop)]
