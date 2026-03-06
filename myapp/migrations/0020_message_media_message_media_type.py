from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0019_reel_reelwatch"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="media",
            field=models.FileField(blank=True, null=True, upload_to="chat_media/"),
        ),
        migrations.AddField(
            model_name="message",
            name="media_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("image", "Image"),
                    ("video", "Video"),
                    ("audio", "Audio"),
                ],
                default="text",
                max_length=10,
            ),
        ),
    ]
