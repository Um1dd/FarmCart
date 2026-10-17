from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("shop", "0007_store_contact_details")]
    operations = [
        migrations.RenameField(
            model_name="adminchallenge",
            old_name="owner_password_digest",
            new_name="authorization_digest",
        )
    ]
