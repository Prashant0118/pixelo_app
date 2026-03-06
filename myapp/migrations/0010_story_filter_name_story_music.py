from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0009_post_is_recommended"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="filter_name",
            field=models.CharField(default="none", max_length=40),
        ),
        migrations.AddField(
            model_name="story",
            name="music",
            field=models.FileField(blank=True, null=True, upload_to="stories/music/"),
        ),
    ]
