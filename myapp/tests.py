from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import shutil
import tempfile


class UploadViewTests(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "Testpass123!"
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_upload_page_loads_for_authenticated_user(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("upload"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload")

    def test_upload_page_shows_post_reel_type_selector(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("upload"))
        self.assertContains(response, "Post")
        self.assertContains(response, "Reel")

    @override_settings(
        CAN_USE_CLOUDINARY=False,
        DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
        STORAGES={
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.StaticFilesStorage",
            },
        },
    )
    def test_chunk_complete_falls_back_to_local_storage(self):
        self.client.login(username=self.username, password=self.password)
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
            upload_id = "test_chunk_upload"
            chunk = SimpleUploadedFile("clip.mp4", b"video-bytes", content_type="video/mp4")

            chunk_response = self.client.post(
                reverse("upload_chunk"),
                {
                    "upload_id": upload_id,
                    "chunk_index": "0",
                    "total_chunks": "1",
                    "filename": "clip.mp4",
                    "chunk": chunk,
                },
            )
            self.assertEqual(chunk_response.status_code, 200)

            complete_response = self.client.post(
                reverse("upload_chunk_complete"),
                {
                    "upload_id": upload_id,
                    "total_chunks": "1",
                    "filename": "clip.mp4",
                    "type": "reel",
                    "caption": "Chunk upload test",
                },
            )

            self.assertEqual(complete_response.status_code, 200)
            data = complete_response.json()
            self.assertTrue(data["ok"])

            self.user.refresh_from_db()
            post = self.user.posts.latest("id")
            self.assertEqual(post.type, "reel")
            self.assertTrue(post.media.name.startswith("posts/"))


class AuthViewTests(TestCase):
    def setUp(self):
        self.password = "Testpass123!"
        self.user = User.objects.create_user(
            username="TestUser",
            email="testuser@example.com",
            password=self.password,
        )

    def test_login_accepts_username_case_insensitively(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": self.password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_accepts_email_case_insensitively(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "TESTUSER@example.com",
                "password": self.password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_register_trims_username_and_email(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "  spaceduser  ",
                "email": "  spaced@example.com  ",
                "password1": self.password,
                "password2": self.password,
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="spaceduser")
        self.assertEqual(created.email, "spaced@example.com")
