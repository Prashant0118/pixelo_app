from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_message_is_seen'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='is_recommended',
            field=models.BooleanField(default=False),
        ),
    ]
