import os
from django.core.files.storage import FileSystemStorage

try:
    from cloudinary_storage.storage import MediaCloudinaryStorage
except Exception:  # pragma: no cover - fallback when cloudinary storage isn't installed
    MediaCloudinaryStorage = None

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".3gpp", ".ogv"}


def _is_video_name(name):
    ext = os.path.splitext(name or "")[1].lower()
    return ext in _VIDEO_EXTS


if MediaCloudinaryStorage:

    class _ImageCloudinaryStorage(MediaCloudinaryStorage):
        RESOURCE_TYPE = "image"


    class _VideoCloudinaryStorage(MediaCloudinaryStorage):
        RESOURCE_TYPE = "video"


    class MediaCloudinaryAutoStorage(MediaCloudinaryStorage):
        """
        Cloudinary storage that routes images/videos to the correct resource_type.
        This ensures videos are uploaded with resource_type="video".
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._image_storage = _ImageCloudinaryStorage()
            self._video_storage = _VideoCloudinaryStorage()

        def _select_storage(self, name):
            return self._video_storage if _is_video_name(name) else self._image_storage

        def _save(self, name, content):
            return self._select_storage(name)._save(name, content)

        def url(self, name):
            return self._select_storage(name).url(name)

        def exists(self, name):
            return self._select_storage(name).exists(name)

        def delete(self, name):
            return self._select_storage(name).delete(name)

else:

    class MediaCloudinaryAutoStorage(FileSystemStorage):
        """
        Local fallback when Cloudinary storage isn't available.
        """

        pass
