from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0011_story_music_suggestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="media",
            field=models.FileField(blank=True, null=True, upload_to="stories/media/"),
        ),
        migrations.AddField(
            model_name="story",
            name="media_type",
            field=models.CharField(default="image", max_length=10),
        ),
        migrations.AlterField(
            model_name="story",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="stories/"),
        ),
    ]
