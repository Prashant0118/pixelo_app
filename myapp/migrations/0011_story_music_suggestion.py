from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0010_story_filter_name_story_music"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="music_suggestion",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
