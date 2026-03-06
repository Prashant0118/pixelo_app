from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0014_story_audience"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorySeen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seen_at", models.DateTimeField(auto_now_add=True)),
                ("story", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seen_by", to="myapp.story")),
                ("viewer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seen_stories", to="auth.user")),
            ],
            options={
                "unique_together": {("viewer", "story")},
            },
        ),
    ]
