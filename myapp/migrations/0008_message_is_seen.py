from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_post_saved_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_seen',
            field=models.BooleanField(default=False),
        ),
    ]
