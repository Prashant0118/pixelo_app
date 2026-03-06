from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0012_story_media_story_media_type_alter_story_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="caption",
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AddField(
            model_name="story",
            name="is_partnership",
            field=models.BooleanField(default=False),
        ),
    ]
