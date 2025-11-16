"""Supabase storage adapter for worker."""
import logging
from pathlib import Path
from uuid import UUID
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

    def download_file(self, storage_path: str, local_path: Path) -> None:
        """
        Download file from storage to local path.

        Args:
            storage_path: Path to the file in storage
            local_path: Local file path to save to
        """
        logger.info(f"Downloading {storage_path} to {local_path}")
        file_bytes = self.client.storage.from_(self.bucket_name).download(storage_path)
        local_path.write_bytes(file_bytes)
        logger.info(f"Downloaded {len(file_bytes)} bytes")

    def upload_file(
        self,
        local_path: Path,
        storage_path: str,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Upload file to storage.

        Args:
            local_path: Local file path to upload
            storage_path: Destination path in storage
            content_type: MIME type of the file

        Returns:
            Public URL of uploaded file
        """
        logger.info(f"Uploading {local_path} to {storage_path}")
        file_bytes = local_path.read_bytes()

        self.client.storage.from_(self.bucket_name).upload(
            storage_path, file_bytes, {"content-type": content_type}
        )

        public_url = self.client.storage.from_(self.bucket_name).get_public_url(
            storage_path
        )
        logger.info(f"Uploaded to {public_url}")
        return public_url


# Global storage instance
storage = SupabaseStorage()
