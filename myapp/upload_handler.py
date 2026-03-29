"""
Custom file upload handlers optimized for large video uploads on constrained platforms.
Handles streaming of large files to disk without excessive memory usage.
"""

import os
import tempfile
from django.core.files.uploadhandler import (
    TemporaryFileUploadHandler as BaseTemporaryFileUploadHandler,
)
from django.conf import settings


class LargeVideoUploadHandler(BaseTemporaryFileUploadHandler):
    """
    Upload handler optimized for large video files.
    - Uses disk streaming for all uploads > FILE_UPLOAD_MAX_MEMORY_SIZE
    - Prevents timeout and memory issues on platforms like Render.com
    - Properly chunks data during streaming
    """

    def upload_complete(self):
        """Called when upload completes."""
        self.file.seek(0)
        return super().upload_complete()

    def receive_data_chunk(self, raw_data, start):
        """
        Write data chunk to temporary file.
        Called iteratively as data is received from client.
        """
        try:
            return super().receive_data_chunk(raw_data, start)
        except OSError as e:
            # Handle disk space or permissions issues gracefully
            raise IOError(f"Upload streaming failed: {e}") from e

    def file_complete(self, file_size):
        """Called when file upload completes."""
        self.file.seek(0)
        return super().file_complete(file_size)
