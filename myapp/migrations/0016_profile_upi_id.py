from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0015_storyseen"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="upi_id",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
