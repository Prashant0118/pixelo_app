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
_AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".weba", ".flac", ".opus"}
_AUDIO_MIMETYPES = {
    "audio/mpeg", "audio/mp4", "audio/aac", "audio/x-m4a", "audio/wav",
    "audio/x-wav", "audio/ogg", "audio/webm", "audio/flac", "audio/opus",
}


def _is_video_name(name):
    """Check if a file is a video based on extension, MIME type, or name heuristics."""
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
    
    # Heuristic for uploads without extensions (e.g. WhatsApp_Video_*).
    raw = os.path.basename(str(name)).lower()
    if not os.path.splitext(raw)[1]:  # No extension
        return "video" in raw
    
    return False


def _is_audio_name(name):
    """Cloudinary stores audio assets with resource_type='video'."""
    if not name:
        return False

    ext = os.path.splitext(str(name))[1].lower()
    if ext in _AUDIO_EXTS:
        return True

    guessed_type, _ = mimetypes.guess_type(str(name))
    if guessed_type and guessed_type.lower() in _AUDIO_MIMETYPES:
        return True

    raw = os.path.basename(str(name)).lower()
    if not os.path.splitext(raw)[1]:
        return "audio" in raw or "music" in raw or "preview" in raw

    return False


def _cloudinary_resource_type(name, content=None):
    content_type = (getattr(content, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type.startswith(("video/", "audio/")):
        return "video"
    return "video" if (_is_video_name(name) or _is_audio_name(name)) else "image"


class LocalMediaStorage(FileSystemStorage):
    """
    Local storage for media files.
    """
    pass


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
            # Initialize upload_options if not present
            if not hasattr(self, 'upload_options'):
                self.upload_options = {}

        def get_folder_name(self, name):
            """Extract folder from name (everything before the last slash)"""
            return os.path.dirname(name) or ""

        def get_file_name(self, name):
            """Extract filename from name (everything after the last slash)"""
            return os.path.basename(name)

        def _save(self, name, content):
            # Get the folder and file_name like the parent does
            folder = self.get_folder_name(name)
            file_name = self.get_file_name(name)
            
            # Cloudinary uses resource_type="video" for both video and audio.
            resource_type = _cloudinary_resource_type(name, content)
            options = {
                'resource_type': resource_type,
                'public_id': file_name,
                'folder': folder,
            }
            
            # Add upload_options if they exist
            if hasattr(self, 'upload_options') and self.upload_options:
                options.update(self.upload_options)
            
            try:
                content.seek(0)
            except Exception:
                pass

            # Upload the file directly
            import cloudinary.uploader
            response = cloudinary.uploader.upload(content, **options)

            # Persist the canonical secure URL when available so templates and
            # model helpers don't have to reconstruct a Cloudinary URL from a
            # potentially normalized public_id/filename pair.
            return response.get("secure_url") or response["public_id"]

        def url(self, name):
            """Generate URL with correct resource_type"""
            if str(name).startswith(("http://", "https://")):
                return str(name)

            resource_type = _cloudinary_resource_type(name)
            try:
                import cloudinary
                from cloudinary.utils import cloudinary_url
                # name is the public_id stored by _save
                url, _options = cloudinary_url(
                    name,
                    resource_type=resource_type,
                    secure=True,
                )
                return url
            except Exception:
                # Fallback to parent implementation
                return super().url(name)

else:

    class MediaCloudinaryAutoStorage(FileSystemStorage):
        """
        Local fallback when Cloudinary storage isn't available.
        """

        pass
