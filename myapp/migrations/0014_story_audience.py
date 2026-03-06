from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0013_story_caption_story_is_partnership"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="audience",
            field=models.CharField(
                choices=[("story", "Your Story"), ("close_friends", "Close Friends")],
                default="story",
                max_length=20,
            ),
        ),
    ]
