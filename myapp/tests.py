from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import shutil
import tempfile
import unittest
from unittest.mock import patch
from myapp.models import Post
from myapp.storage import MediaCloudinaryAutoStorage
from myapp import storage as storage_module


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

    @override_settings(UPLOAD_PARALLEL_CHUNKS=1)
    def test_upload_page_uses_safe_chunk_parallelism(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("upload"))
        self.assertContains(response, "const PARALLEL_UPLOADS = 1;")

    @override_settings(
        CAN_USE_CLOUDINARY=True,
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="demo-key",
        CLOUDINARY_API_SECRET="demo-secret",
        CLOUDINARY_VIDEO_MAX_BYTES=100,
    )
    def test_upload_page_exposes_cloudinary_video_limit(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("upload"))
        self.assertContains(response, "const CLOUDINARY_VIDEO_MAX_BYTES = 100;")

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

    def test_register_logs_user_in_immediately(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "NewUser",
                "email": "NewUser@example.com",
                "password1": self.password,
                "password2": self.password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        created = User.objects.get(username="newuser")
        self.assertEqual(created.email, "newuser@example.com")


class PostMediaUrlTests(TestCase):
    @override_settings(
        CAN_USE_CLOUDINARY=True,
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="demo-key",
        CLOUDINARY_API_SECRET="demo-secret",
    )
    def test_media_url_returns_local_media_path_when_available(self):
        user = User.objects.create_user(username="mediauser", password="Testpass123!")
        post = Post.objects.create(user=user, type="post")
        post.media.name = "posts/sample-image.jpg"

        media_url = post.media_url

        self.assertEqual(media_url, "/media/posts/sample-image.jpg")


class MediaServingTests(TestCase):
    @override_settings(
        CAN_USE_CLOUDINARY=False,
        SERVE_MEDIA=True,
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
    def test_uploaded_image_is_served_from_media_route(self):
        user = User.objects.create_user(username="imguser", password="Testpass123!")
        self.client.login(username="imguser", password="Testpass123!")
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
            image = SimpleUploadedFile("photo.jpg", b"fake-image-bytes", content_type="image/jpeg")
            response = self.client.post(
                reverse("upload"),
                {
                    "type": "post",
                    "caption": "Image post",
                    "media": image,
                },
            )

            self.assertEqual(response.status_code, 302)
            post = Post.objects.latest("id")
            self.assertTrue(post.media_url.startswith("/media/posts/"))

            media_response = self.client.get(post.media_url)
            self.assertEqual(media_response.status_code, 200)


class ChunkCompleteUploadTests(TestCase):
    def setUp(self):
        self.password = "Testpass123!"
        self.user = User.objects.create_user(username="chunkuser", password=self.password)
        self.client.login(username="chunkuser", password=self.password)

    @override_settings(
        CAN_USE_CLOUDINARY=True,
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="demo-key",
        CLOUDINARY_API_SECRET="demo-secret",
    )
    @patch("cloudinary.uploader.upload_large")
    @patch("cloudinary.uploader.upload")
    @patch("os.path.getsize", return_value=101 * 1024 * 1024)
    def test_chunk_complete_uses_upload_large_for_large_files(self, mock_getsize, mock_upload, mock_upload_large):
        mock_upload_large.return_value = {
            "secure_url": "https://res.cloudinary.com/demo/video/upload/v1/posts/big.mp4",
        }
        upload_id = "large_chunk_upload"
        chunk = SimpleUploadedFile("big.mp4", b"video-bytes", content_type="video/mp4")

        chunk_response = self.client.post(
            reverse("upload_chunk"),
            {
                "upload_id": upload_id,
                "chunk_index": "0",
                "total_chunks": "1",
                "filename": "big.mp4",
                "chunk": chunk,
            },
        )
        self.assertEqual(chunk_response.status_code, 200)

        complete_response = self.client.post(
            reverse("upload_chunk_complete"),
            {
                "upload_id": upload_id,
                "total_chunks": "1",
                "filename": "big.mp4",
                "type": "reel",
                "caption": "Large video",
            },
        )

        self.assertEqual(complete_response.status_code, 200)
        mock_upload_large.assert_called_once()
        mock_upload.assert_not_called()

    @override_settings(
        CAN_USE_CLOUDINARY=True,
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="demo-key",
        CLOUDINARY_API_SECRET="demo-secret",
        CLOUDINARY_VIDEO_MAX_BYTES=5,
    )
    def test_chunk_complete_rejects_video_above_cloudinary_limit(self):
        upload_id = "cloudinary_limit_upload"
        chunk = SimpleUploadedFile("big.mp4", b"video-bytes", content_type="video/mp4")

        chunk_response = self.client.post(
            reverse("upload_chunk"),
            {
                "upload_id": upload_id,
                "chunk_index": "0",
                "total_chunks": "1",
                "filename": "big.mp4",
                "chunk": chunk,
            },
        )
        self.assertEqual(chunk_response.status_code, 200)

        complete_response = self.client.post(
            reverse("upload_chunk_complete"),
            {
                "upload_id": upload_id,
                "total_chunks": "1",
                "filename": "big.mp4",
                "type": "reel",
                "caption": "Too large for cloud plan",
            },
        )

        self.assertEqual(complete_response.status_code, 400)
        self.assertIn("Current cloud video limit", complete_response.json()["error"])


class CloudinaryStorageTests(TestCase):
    @unittest.skipIf(
        getattr(storage_module, "MediaCloudinaryStorage", None) is None,
        "Cloudinary storage backend is not available in this test environment.",
    )
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_storage_returns_secure_url(self, mock_upload):
        mock_upload.return_value = {
            "public_id": "posts/download",
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/posts/download.jpg",
        }
        storage = MediaCloudinaryAutoStorage()
        content = SimpleUploadedFile("download.jpg", b"img", content_type="image/jpeg")

        saved_name = storage._save("posts/download.jpg", content)

        self.assertEqual(
            saved_name,
            "https://res.cloudinary.com/demo/image/upload/v1/posts/download.jpg",
        )
