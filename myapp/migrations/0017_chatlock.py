from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0016_profile_upi_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=256)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=models.CASCADE, related_name="chat_locks", to=settings.AUTH_USER_MODEL)),
                ("target", models.ForeignKey(on_delete=models.CASCADE, related_name="locked_for_users", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("owner", "target")},
            },
        ),
    ]
