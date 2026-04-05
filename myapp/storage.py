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

    class MediaCloudinaryAutoStorage(MediaCloudinaryStorage):
        """
        Cloudinary storage that routes images/videos to the correct resource_type.
        This ensures videos are uploaded with resource_type="video".
        """

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
            
            # Create options with correct resource_type
            resource_type = "video" if _is_video_name(name) else "image"
            options = {
                'resource_type': resource_type,
                'public_id': file_name,
                'folder': folder,
            }
            
            if self.upload_options:
                options.update(self.upload_options)
            
            print(f"[storage-debug] _save: name={name}, resource_type={resource_type}")
            
            # Upload the file directly
            import cloudinary.uploader
            response = cloudinary.uploader.upload(content, **options)
            
            # Return the public_id
            return response['public_id']

else:

    class MediaCloudinaryAutoStorage(FileSystemStorage):
        """
        Local fallback when Cloudinary storage isn't available.
        """

        pass
