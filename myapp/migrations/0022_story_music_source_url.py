from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0021_storymusic_storymusicimport"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="music_source_url",
            field=models.URLField(blank=True),
        ),
    ]
