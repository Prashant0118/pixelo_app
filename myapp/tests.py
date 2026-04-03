from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


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

