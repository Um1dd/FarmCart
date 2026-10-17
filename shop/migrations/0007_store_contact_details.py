from django.db import migrations


def contact_details(apps, schema_editor):
    apps.get_model("shop", "StoreSettings").objects.update_or_create(
        pk=1,
        defaults={
            "whatsapp": "+994772506587",
            "phone": "+994772506587",
            "instagram_username": "l.umidw",
            "instagram_url": "https://www.instagram.com/l.umidw/",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("shop", "0006_product_stock_storesettings_instagram_url_and_more")]
    operations = [migrations.RunPython(contact_details, migrations.RunPython.noop)]
