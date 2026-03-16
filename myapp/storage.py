import os

from cloudinary_storage.storage import MediaCloudinaryStorage, RESOURCE_TYPES


VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".3gp",
    ".3gpp",
    ".ogv",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".oga",
    ".ogg",
    ".opus",
    ".webm",
}


class MediaCloudinaryAutoStorage(MediaCloudinaryStorage):
    """
    Cloudinary storage that picks image vs video resource type based on extension.
    This avoids "Invalid image file" for videos and produces correct delivery URLs.
    """
    def _get_resource_type(self, name):
        ext = os.path.splitext(name or "")[1].lower()
        if ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
            return RESOURCE_TYPES["VIDEO"]
        return RESOURCE_TYPES["IMAGE"]
