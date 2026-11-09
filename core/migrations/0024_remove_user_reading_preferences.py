from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_user_reading_preferences"),
    ]

    operations = [
        migrations.RemoveField(model_name="user", name="reading_preferences"),
        migrations.RemoveField(model_name="user", name="reading_preferences_status"),
    ]
