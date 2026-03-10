from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0022_story_music_source_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="post",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="notifications", to="myapp.post"),
        ),
    ]
