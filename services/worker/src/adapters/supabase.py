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
        """Initialize the Supabase storage client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self.bucket_name = "videos"
        self.storage_url = settings.supabase_url  # Base URL for constructing public URLs

    def download_file(self, storage_path: str, local_path: Path) -> None:
        """
        Download file from storage to local path.

        Args:
            storage_path: Path to the file in storage
            local_path: Local file path to save to

        Returns:
            None: This function does not return a value.
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
        Upload file to storage. Idempotent - if file exists, returns existing URL.

        Args:
            local_path: Local file path to upload
            storage_path: Destination path in storage
            content_type: MIME type of the file

        Returns:
            str: Public URL of uploaded file

        Raises:
            Exception: If upload fails and file doesn't already exist
        """
        logger.info(f"Uploading {local_path.name} ({local_path.stat().st_size} bytes) to {storage_path}")

        # Verify local file exists
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        # Read file bytes
        try:
            file_bytes = local_path.read_bytes()
            logger.debug(f"Read {len(file_bytes)} bytes from {local_path}")
        except Exception as e:
            logger.error(f"Failed to read local file {local_path}: {e}")
            raise

        # Try to upload the file
        # If it already exists, we'll get a 409 Duplicate error which we handle gracefully
        try:
            logger.info(f"Uploading {len(file_bytes)} bytes to {storage_path}")
            self.client.storage.from_(self.bucket_name).upload(
                storage_path,
                file_bytes,
                {"content-type": content_type, "upsert": "false"}  # Don't overwrite existing
            )
            logger.info(f"Successfully uploaded to {storage_path}")
        except Exception as e:
            error_str = str(e)
            # If we get a 409 Duplicate error, that's fine (file already exists)
            if "409" in error_str or "Duplicate" in error_str or "already exists" in error_str:
                logger.info(f"File already exists at {storage_path}, using existing file")
            else:
                # Log the full error for debugging
                logger.error(f"Upload failed for {storage_path}: {error_str}", exc_info=True)
                raise

        # Get and return public URL
        try:
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(storage_path)
            logger.info(f"Thumbnail URL: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Failed to get public URL for {storage_path}: {e}")
            # Return a fallback URL pattern (Supabase standard format)
            return f"{self.client.storage_url}/object/public/{self.bucket_name}/{storage_path}"


# Global storage instance
storage = SupabaseStorage()
