from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0020_message_media_message_media_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StoryMusic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=140)),
                ("artist", models.CharField(blank=True, max_length=140)),
                (
                    "section",
                    models.CharField(
                        choices=[
                            ("for_you", "For You"),
                            ("new", "New"),
                            ("trending", "Trending"),
                            ("admin", "Admin Picks"),
                        ],
                        default="admin",
                        max_length=20,
                    ),
                ),
                ("youtube_video_id", models.CharField(blank=True, db_index=True, max_length=32)),
                ("youtube_url", models.URLField(blank=True)),
                ("audio", models.FileField(blank=True, null=True, upload_to="stories/music/library/")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="story_music_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="StoryMusicImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=160)),
                (
                    "section",
                    models.CharField(
                        choices=[
                            ("for_you", "For You"),
                            ("new", "New"),
                            ("trending", "Trending"),
                            ("admin", "Admin Picks"),
                        ],
                        default="trending",
                        max_length=20,
                    ),
                ),
                ("max_results", models.PositiveSmallIntegerField(default=25)),
                ("is_active", models.BooleanField(default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_imported_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
