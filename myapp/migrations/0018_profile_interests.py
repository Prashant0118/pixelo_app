from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0017_chatlock"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="interests",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
