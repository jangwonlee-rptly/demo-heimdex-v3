"""Supabase storage adapter."""
import logging
from uuid import UUID, uuid4
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase storage client wrapper."""

    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str = "videos"):
        """Initialize the Supabase storage client.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key for authentication
            bucket_name: Name of the storage bucket (default: "videos")
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.bucket_name = bucket_name

    def create_upload_url(self, user_id: UUID, file_extension: str = "mp4") -> tuple[str, str]:
        """
        Create a signed upload URL for video upload.

        Args:
            user_id: ID of the user uploading the video
            file_extension: File extension (default: mp4)

        Returns:
            tuple[str, str]: Tuple of (upload_url, storage_path)
        """
        # Generate unique storage path
        video_id = uuid4()
        storage_path = f"{user_id}/{video_id}.{file_extension}"

        # Create signed upload URL (valid for 2 hours)
        response = self.client.storage.from_(self.bucket_name).create_signed_upload_url(
            storage_path
        )

        return response["signed_url"], storage_path

    def create_signed_upload_url(self, storage_path: str, expires_in: int = 7200) -> str:
        """
        Create a signed upload URL for a specific storage path.

        Args:
            storage_path: Path where the file will be stored (e.g., "persons/{owner_id}/{person_id}/refs/{photo_id}.jpg")
            expires_in: Expiration time in seconds (default: 7200 = 2 hours)

        Returns:
            str: Signed upload URL
        """
        response = self.client.storage.from_(self.bucket_name).create_signed_upload_url(
            storage_path
        )
        return response["signed_url"]

    def get_public_url(self, storage_path: str) -> str:
        """
        Get public URL for a stored file.

        Args:
            storage_path: Path to the file in storage

        Returns:
            str: Public URL
        """
        return self.client.storage.from_(self.bucket_name).get_public_url(storage_path)

    def get_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for downloading a file.

        Args:
            storage_path: Path to the file in storage
            expires_in: Expiration time in seconds (default: 3600 = 1 hour)

        Returns:
            str: Presigned download URL
        """
        logger.info(f"Creating signed URL for {storage_path} (expires in {expires_in}s)")
        response = self.client.storage.from_(self.bucket_name).create_signed_url(
            storage_path,
            expires_in
        )
        logger.debug(f"Signed URL response: {response}")

        # Supabase Python SDK returns dict with 'signedURL' key
        # (different from create_signed_upload_url which uses 'signed_url')
        signed_url = response.get("signedURL") or response.get("signed_url") or response.get("signedUrl")

        if not signed_url:
            logger.error(f"Failed to get signed URL. Response: {response}")
            raise ValueError(f"No signed URL in response: {response}")

        return signed_url

    def download_file(self, storage_path: str) -> bytes:
        """
        Download file from storage.

        Args:
            storage_path: Path to the file in storage

        Returns:
            bytes: File contents as bytes
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
            str: Public URL of uploaded file
        """
        self.client.storage.from_(self.bucket_name).upload(
            storage_path,
            file_data,
            {"content-type": content_type}
        )
        return self.get_public_url(storage_path)


# DEPRECATED: Global instance removed for Phase 1 refactor.
# Use dependency injection instead via get_storage() from dependencies.py
storage: SupabaseStorage = None  # type: ignore
