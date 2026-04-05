import os
import mimetypes
from django.core.files.storage import FileSystemStorage

try:
    from cloudinary_storage.storage import MediaCloudinaryStorage
except Exception:  # pragma: no cover - fallback when cloudinary storage isn't installed
    MediaCloudinaryStorage = None

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".3gpp", ".ogv", ".flv", ".wmv", ".m3u8", ".ts", ".mts"}
_VIDEO_MIMETYPES = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/3gpp", "video/ogg", "video/x-flv",
    "video/x-ms-wmv", "application/x-mpegURL", "video/mp2t"
}


def _is_video_name(name):
    """Check if a file is a video based on extension and MIME type."""
    if not name:
        return False
    
    # Check extension first (fastest)
    ext = os.path.splitext(str(name))[1].lower()
    if ext in _VIDEO_EXTS:
        return True
    
    # Fallback to MIME type detection
    guessed_type, _ = mimetypes.guess_type(str(name))
    if guessed_type and guessed_type.lower() in _VIDEO_MIMETYPES:
        return True
    
    return False


if MediaCloudinaryStorage:

    class _ImageCloudinaryStorage(MediaCloudinaryStorage):
        resource_type = "image"


    class _VideoCloudinaryStorage(MediaCloudinaryStorage):
        resource_type = "video"


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
