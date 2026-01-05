"""Person reference photo processing logic."""
import logging
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class PersonPhotoProcessor:
    """Processes reference photos for person search."""

    def __init__(self, db, storage, clip_embedder=None):
        """Initialize processor.

        Args:
            db: Database adapter
            storage: Storage adapter
            clip_embedder: Optional CLIP embedder
        """
        self.db = db
        self.storage = storage
        self.clip_embedder = clip_embedder

    def process_photo(self, photo_id: UUID) -> None:
        """Process a reference photo: download, embed, aggregate.

        Args:
            photo_id: UUID of the photo to process

        Raises:
            Exception: Any processing error (logged and saved to DB)
        """
        logger.info(f"Processing reference photo {photo_id}")

        # Load photo record
        photo = self.db.get_person_reference_photo(photo_id)
        if not photo:
            raise ValueError(f"Photo {photo_id} not found")

        person_id = UUID(photo["person_id"])
        storage_path = photo["storage_path"]
        state = photo["state"]

        # Idempotency: skip if already READY
        if state == "READY":
            logger.info(f"Photo {photo_id} already READY, skipping")
            return

        # Idempotency: for PROCESSING, proceed anyway (simple rule)
        # In production, could add stale timeout check here

        # Check CLIP embedder availability
        if not self.clip_embedder:
            raise ValueError("CLIP embedder not available")

        try:
            # Update state to PROCESSING
            self.db.update_person_photo_state(photo_id, "PROCESSING")
            logger.info(f"Photo {photo_id} marked as PROCESSING")

            # Download photo to temporary directory
            with TemporaryDirectory() as tmpdir:
                local_path = Path(tmpdir) / f"photo_{photo_id}.jpg"

                logger.info(f"Downloading photo from {storage_path}")
                photo_data = self.storage.download_file(storage_path)
                local_path.write_bytes(photo_data)

                # Generate CLIP embedding
                logger.info(f"Generating CLIP embedding for {local_path}")
                embedding, metadata = self.clip_embedder.create_visual_embedding(
                    image_path=local_path,
                    timeout_s=5.0,
                )

                if not embedding:
                    error_msg = metadata.error if metadata and metadata.error else "CLIP embedding failed"
                    raise ValueError(error_msg)

                # Validate embedding dimension
                if len(embedding) != 512:
                    raise ValueError(f"Invalid embedding dimension: {len(embedding)}, expected 512")

                # Normalize embedding if not already normalized
                embedding_array = np.array(embedding)
                norm = np.linalg.norm(embedding_array)
                if abs(norm - 1.0) > 0.01:  # Not normalized
                    logger.info(f"Normalizing embedding (norm={norm:.4f})")
                    embedding_array = embedding_array / norm
                    embedding = embedding_array.tolist()

                # Compute basic quality score (v1 heuristic: use norm as proxy)
                # Higher norm (before normalization) suggests stronger signal
                quality_score = min(1.0, norm / 10.0)  # Simple heuristic

                logger.info(
                    f"Embedding generated: dim={len(embedding)}, "
                    f"quality_score={quality_score:.3f}"
                )

                # Update photo with embedding
                self.db.update_person_photo_embedding(
                    photo_id=photo_id,
                    embedding=embedding,
                    quality_score=quality_score,
                    state="READY",
                )

                logger.info(f"Photo {photo_id} marked as READY")

            # Update person query embedding (aggregate of all READY photos)
            self._update_person_query_embedding(person_id)

            logger.info(f"Successfully processed photo {photo_id}")

        except Exception as e:
            error_message = str(e)[:500]  # Truncate
            logger.error(f"Failed to process photo {photo_id}: {error_message}", exc_info=True)

            # Mark as FAILED
            self.db.update_person_photo_failed(photo_id, error_message)

            # Re-raise so Dramatiq logs it
            raise

    def _update_person_query_embedding(self, person_id: UUID) -> None:
        """Update person query embedding from READY photos.

        Args:
            person_id: UUID of the person
        """
        logger.info(f"Updating query embedding for person {person_id}")

        # Get all READY photo embeddings
        embeddings = self.db.get_ready_photo_embeddings(person_id)

        if not embeddings:
            logger.warning(f"No READY embeddings found for person {person_id}")
            return

        logger.info(f"Aggregating {len(embeddings)} embeddings for person {person_id}")

        # Compute normalized mean
        embeddings_array = np.array(embeddings)
        mean_embedding = np.mean(embeddings_array, axis=0)

        # Normalize
        norm = np.linalg.norm(mean_embedding)
        if norm > 0:
            mean_embedding = mean_embedding / norm

        # Update person
        self.db.update_person_query_embedding(
            person_id=person_id,
            embedding=mean_embedding.tolist(),
        )

        logger.info(f"Updated query embedding for person {person_id} (norm={norm:.4f})")
