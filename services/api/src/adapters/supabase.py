"""Supabase storage adapter."""
import logging
from uuid import UUID, uuid4
from supabase import create_client, Client

from ..config import settings

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase storage client wrapper."""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self.bucket_name = "videos"

    def create_upload_url(self, user_id: UUID, file_extension: str = "mp4") -> tuple[str, str]:
        """
        Create a signed upload URL for video upload.

        Args:
            user_id: ID of the user uploading the video
            file_extension: File extension (default: mp4)

        Returns:
            Tuple of (upload_url, storage_path)
        """
        # Generate unique storage path
        video_id = uuid4()
        storage_path = f"{user_id}/{video_id}.{file_extension}"

        # Create signed upload URL (valid for 2 hours)
        response = self.client.storage.from_(self.bucket_name).create_signed_upload_url(
            storage_path
        )

        return response["signed_url"], storage_path

    def get_public_url(self, storage_path: str) -> str:
        """
        Get public URL for a stored file.

        Args:
            storage_path: Path to the file in storage

        Returns:
            Public URL
        """
        return self.client.storage.from_(self.bucket_name).get_public_url(storage_path)

    def download_file(self, storage_path: str) -> bytes:
        """
        Download file from storage.

        Args:
            storage_path: Path to the file in storage

        Returns:
            File contents as bytes
        """
        return self.client.storage.from_(self.bucket_name).download(storage_path)

    def upload_file(self, storage_path: str, file_data: bytes, content_type: str = "image/jpeg") -> str:
        """
        Upload file to storage.

        Args:
            storage_path: Destination path in storage
            file_data: File contents as bytes
            content_type: MIME type of the file

        Returns:
            Public URL of uploaded file
        """
        self.client.storage.from_(self.bucket_name).upload(
            storage_path,
            file_data,
            {"content-type": content_type}
        )
        return self.get_public_url(storage_path)


# Global storage instance
storage = SupabaseStorage()
