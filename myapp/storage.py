import os
from django.core.files.storage import FileSystemStorage


class MediaCloudinaryAutoStorage(FileSystemStorage):
    """
    Backwards-compatible storage placeholder.
    Cloudinary was removed; this class now behaves like FileSystemStorage
    to keep code importing `MediaCloudinaryAutoStorage` working.
    """

    def _get_resource_type(self, name):
        ext = os.path.splitext(name or "")[1].lower()
        if ext in {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".3gpp", ".ogv"}:
            return "video"
        return "image"

    def _upload(self, name, content):
        # Save using default FileSystemStorage behavior.
        return self.save(name, content)
