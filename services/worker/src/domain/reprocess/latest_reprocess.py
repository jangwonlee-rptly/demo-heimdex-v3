"""
Latest Embedding Reprocessing Pipeline - Single Source of Truth

This module defines the canonical reprocessing specification for all embedding methods.
When adding new embedding types or updating embedding logic, update LATEST_EMBEDDING_SPEC_VERSION
and the ReprocessSpec to ensure reprocessing uses the latest methods.

LATEST_EMBEDDING_SPEC_VERSION tracks which embedding pipeline version is being used.
Update this constant whenever you modify the embedding generation logic.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

# Version constant - update this whenever embedding logic changes
LATEST_EMBEDDING_SPEC_VERSION = "2026-01-06"

logger = logging.getLogger(__name__)


class ReprocessScope(str, Enum):
    """Scope of reprocessing operation"""
    VIDEO = "video"  # Reprocess a single video
    OWNER = "owner"  # Reprocess all videos for an owner_id
    ALL = "all"      # Reprocess all videos in the system (admin only)


class EmbeddingStepType(str, Enum):
    """Types of embedding regeneration steps"""
    SCENE_TEXT_EMBEDDINGS = "scene_text_embeddings"  # transcript, visual, summary
    SCENE_CLIP_EMBEDDINGS = "scene_clip_embeddings"  # CLIP visual embeddings
    SCENE_PERSON_EMBEDDINGS = "scene_person_embeddings"  # thumbnail-based person detection
    PERSON_PHOTO_EMBEDDINGS = "person_photo_embeddings"  # reference photo CLIP embeddings
    PERSON_QUERY_EMBEDDING = "person_query_embedding"  # aggregated person query embedding
    OPENSEARCH_REINDEX = "opensearch_reindex"  # reindex scenes to OpenSearch


@dataclass
class EmbeddingStep:
    """Defines a single embedding regeneration step"""
    step_type: EmbeddingStepType
    enabled: bool
    description: str
    idempotent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_type": self.step_type.value,
            "enabled": self.enabled,
            "description": self.description,
            "idempotent": self.idempotent,
        }


@dataclass
class ReprocessSpec:
    """
    Specification for the latest embedding methods.

    This is the SINGLE SOURCE OF TRUTH for what "latest embedding methods" means.

    When you update embedding generation logic (e.g., new CLIP model, updated normalization,
    new embedding channels), update this spec and increment LATEST_EMBEDDING_SPEC_VERSION.
    """
    version: str
    steps: List[EmbeddingStep]

    @classmethod
    def get_latest_spec(cls) -> "ReprocessSpec":
        """
        Returns the latest embedding reprocessing specification.

        This defines all embedding types that should be regenerated during reprocessing:

        1. Scene Text Embeddings (OpenAI text-embedding-3-small, 1536d):
           - embedding_transcript: Pure ASR transcript
           - embedding_visual: Visual description + tags
           - embedding_summary: Optional summary (currently disabled)
           - Uses multi-channel architecture (v3-multi)

        2. Scene CLIP Embeddings (OpenAI ViT-B-32, 512d):
           - embedding_visual_clip: Visual embedding from scene thumbnail
           - Backend: local CPU or RunPod GPU (configurable)

        3. Scene Person Embeddings (CLIP, 512d):
           - Thumbnail-based person detection embeddings
           - Stored in scene_person_embeddings table
           - kind="thumbnail", ordinal=0

        4. Person Reference Photo Embeddings (CLIP, 512d):
           - Individual photo embeddings
           - Stored in person_reference_photos.embedding

        5. Person Query Embeddings (CLIP, 512d):
           - Aggregated mean of all READY photo embeddings
           - Stored in persons.query_embedding

        6. OpenSearch Reindexing:
           - Reindex scenes to OpenSearch for BM25 lexical search
        """
        return cls(
            version=LATEST_EMBEDDING_SPEC_VERSION,
            steps=[
                EmbeddingStep(
                    step_type=EmbeddingStepType.SCENE_TEXT_EMBEDDINGS,
                    enabled=True,
                    description="Regenerate scene text embeddings (transcript, visual, summary channels) using OpenAI text-embedding-3-small",
                    idempotent=True,
                ),
                EmbeddingStep(
                    step_type=EmbeddingStepType.SCENE_CLIP_EMBEDDINGS,
                    enabled=True,
                    description="Regenerate scene CLIP visual embeddings using ViT-B-32 from scene thumbnails",
                    idempotent=True,
                ),
                EmbeddingStep(
                    step_type=EmbeddingStepType.SCENE_PERSON_EMBEDDINGS,
                    enabled=True,
                    description="Regenerate scene person embeddings from thumbnails for person-aware visual search",
                    idempotent=True,
                ),
                EmbeddingStep(
                    step_type=EmbeddingStepType.PERSON_PHOTO_EMBEDDINGS,
                    enabled=True,
                    description="Regenerate person reference photo CLIP embeddings",
                    idempotent=True,
                ),
                EmbeddingStep(
                    step_type=EmbeddingStepType.PERSON_QUERY_EMBEDDING,
                    enabled=True,
                    description="Recompute aggregated person query embeddings from READY photos",
                    idempotent=True,
                ),
                EmbeddingStep(
                    step_type=EmbeddingStepType.OPENSEARCH_REINDEX,
                    enabled=True,
                    description="Reindex scenes to OpenSearch for lexical search",
                    idempotent=True,
                ),
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass
class ReprocessRequest:
    """Request parameters for reprocessing"""
    scope: ReprocessScope
    video_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    force: bool = False  # Force regeneration even if embeddings exist
    since: Optional[datetime] = None  # Only reprocess videos updated after this date
    spec_version: str = LATEST_EMBEDDING_SPEC_VERSION

    def validate(self) -> None:
        """Validate request parameters"""
        if self.scope == ReprocessScope.VIDEO and not self.video_id:
            raise ValueError("video_id required for VIDEO scope")
        if self.scope == ReprocessScope.OWNER and not self.owner_id:
            raise ValueError("owner_id required for OWNER scope")
        if self.scope == ReprocessScope.ALL and (self.video_id or self.owner_id):
            raise ValueError("video_id and owner_id must be None for ALL scope")


@dataclass
class ReprocessProgress:
    """Progress tracking for reprocessing operations"""
    request: ReprocessRequest
    started_at: datetime
    completed_at: Optional[datetime] = None

    videos_total: int = 0
    videos_processed: int = 0
    videos_skipped: int = 0
    videos_failed: int = 0

    scenes_total: int = 0
    scenes_processed: int = 0
    scenes_skipped: int = 0
    scenes_failed: int = 0

    person_photos_total: int = 0
    person_photos_processed: int = 0
    person_photos_failed: int = 0

    persons_total: int = 0
    persons_processed: int = 0
    persons_failed: int = 0

    errors: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_version": self.request.spec_version,
            "scope": self.request.scope.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "videos_total": self.videos_total,
            "videos_processed": self.videos_processed,
            "videos_skipped": self.videos_skipped,
            "videos_failed": self.videos_failed,
            "scenes_total": self.scenes_total,
            "scenes_processed": self.scenes_processed,
            "scenes_skipped": self.scenes_skipped,
            "scenes_failed": self.scenes_failed,
            "person_photos_total": self.person_photos_total,
            "person_photos_processed": self.person_photos_processed,
            "person_photos_failed": self.person_photos_failed,
            "persons_total": self.persons_total,
            "persons_processed": self.persons_processed,
            "persons_failed": self.persons_failed,
            "error_count": len(self.errors),
        }


class ReprocessRunner:
    """
    Orchestrates the reprocessing pipeline using the latest embedding spec.

    This runner ensures all embedding regeneration uses the current pipeline logic.
    It's designed to be called from Dramatiq actors with proper dependency injection.
    """

    def __init__(
        self,
        db,
        storage,
        opensearch,
        openai,
        clip_embedder,
        settings,
    ):
        """
        Initialize reprocess runner with injected dependencies.

        Args:
            db: Database adapter
            storage: Storage adapter
            opensearch: OpenSearch client
            openai: OpenAI client
            clip_embedder: CLIP embedder adapter
            settings: Settings object
        """
        from src.domain.sidecar_builder import SidecarBuilder
        from src.domain.person_photo_processor import PersonPhotoProcessor

        self.db = db
        self.storage = storage
        self.opensearch = opensearch
        self.openai = openai
        self.clip_embedder = clip_embedder
        self.settings = settings

        # Create domain processors
        self.sidecar_builder = SidecarBuilder(
            db=db,
            storage=storage,
            openai=openai,
            clip_embedder=clip_embedder,
            settings=settings,
        )

        self.person_processor = PersonPhotoProcessor(
            db=db,
            storage=storage,
            clip_embedder=clip_embedder,
            settings=settings,
        )

    def run_reprocess(self, request: ReprocessRequest) -> ReprocessProgress:
        """
        Execute reprocessing pipeline according to request scope.

        Args:
            request: Reprocessing request parameters

        Returns:
            ReprocessProgress with execution results
        """
        request.validate()

        spec = ReprocessSpec.get_latest_spec()
        progress = ReprocessProgress(
            request=request,
            started_at=datetime.utcnow(),
        )

        logger.info(
            "Starting reprocessing",
            extra={
                "spec_version": spec.version,
                "scope": request.scope.value,
                "video_id": str(request.video_id) if request.video_id else None,
                "owner_id": str(request.owner_id) if request.owner_id else None,
                "force": request.force,
            }
        )

        try:
            if request.scope == ReprocessScope.VIDEO:
                self._reprocess_video(request.video_id, request, spec, progress)
            elif request.scope == ReprocessScope.OWNER:
                self._reprocess_owner(request.owner_id, request, spec, progress)
            elif request.scope == ReprocessScope.ALL:
                self._reprocess_all(request, spec, progress)

            progress.completed_at = datetime.utcnow()

            logger.info(
                "Reprocessing completed",
                extra=progress.to_dict()
            )
        except Exception as e:
            logger.error(
                "Reprocessing failed",
                extra={
                    "error": str(e),
                    "spec_version": spec.version,
                    "scope": request.scope.value,
                },
                exc_info=True
            )
            progress.errors.append({
                "error": str(e),
                "type": type(e).__name__,
            })
            raise

        return progress

    def _reprocess_video(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        spec: ReprocessSpec,
        progress: ReprocessProgress,
    ) -> None:
        """Reprocess a single video"""
        logger.info(f"Reprocessing video {video_id}")

        try:
            # Get video
            video = self.db.get_video(video_id)
            if not video:
                logger.warning(f"Video {video_id} not found")
                progress.videos_skipped += 1
                return

            progress.videos_total = 1

            # Execute enabled steps
            self._execute_video_steps(video_id, request, spec, progress)

            progress.videos_processed += 1

        except Exception as e:
            logger.error(f"Failed to reprocess video {video_id}: {e}", exc_info=True)
            progress.videos_failed += 1
            progress.errors.append({
                "video_id": str(video_id),
                "error": str(e),
                "type": type(e).__name__,
            })

    def _reprocess_owner(
        self,
        owner_id: UUID,
        request: ReprocessRequest,
        spec: ReprocessSpec,
        progress: ReprocessProgress,
    ) -> None:
        """Reprocess all videos for an owner"""
        logger.info(f"Reprocessing videos for owner {owner_id}")

        # Get all videos for owner
        videos = self.db.get_videos_for_reprocess(
            owner_id=owner_id,
            since=request.since,
        )

        progress.videos_total = len(videos)
        logger.info(f"Found {len(videos)} videos for owner {owner_id}")

        for video in videos:
            try:
                self._execute_video_steps(video.id, request, spec, progress)
                progress.videos_processed += 1
            except Exception as e:
                logger.error(f"Failed to reprocess video {video.id}: {e}", exc_info=True)
                progress.videos_failed += 1
                progress.errors.append({
                    "video_id": str(video.id),
                    "error": str(e),
                    "type": type(e).__name__,
                })

    def _reprocess_all(
        self,
        request: ReprocessRequest,
        spec: ReprocessSpec,
        progress: ReprocessProgress,
    ) -> None:
        """Reprocess all videos in the system"""
        logger.info("Reprocessing all videos")

        # Get all videos
        videos = self.db.get_videos_for_reprocess(
            owner_id=None,
            since=request.since,
        )

        progress.videos_total = len(videos)
        logger.info(f"Found {len(videos)} total videos")

        for video in videos:
            try:
                self._execute_video_steps(video.id, request, spec, progress)
                progress.videos_processed += 1
            except Exception as e:
                logger.error(f"Failed to reprocess video {video.id}: {e}", exc_info=True)
                progress.videos_failed += 1
                progress.errors.append({
                    "video_id": str(video.id),
                    "error": str(e),
                    "type": type(e).__name__,
                })

    def _execute_video_steps(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        spec: ReprocessSpec,
        progress: ReprocessProgress,
    ) -> None:
        """Execute all enabled reprocessing steps for a video"""

        for step in spec.steps:
            if not step.enabled:
                continue

            try:
                if step.step_type == EmbeddingStepType.SCENE_TEXT_EMBEDDINGS:
                    self._regenerate_scene_text_embeddings(video_id, request, progress)

                elif step.step_type == EmbeddingStepType.SCENE_CLIP_EMBEDDINGS:
                    self._regenerate_scene_clip_embeddings(video_id, request, progress)

                elif step.step_type == EmbeddingStepType.SCENE_PERSON_EMBEDDINGS:
                    self._regenerate_scene_person_embeddings(video_id, request, progress)

                elif step.step_type == EmbeddingStepType.PERSON_PHOTO_EMBEDDINGS:
                    self._regenerate_person_photo_embeddings(video_id, request, progress)

                elif step.step_type == EmbeddingStepType.PERSON_QUERY_EMBEDDING:
                    self._regenerate_person_query_embeddings(video_id, request, progress)

                elif step.step_type == EmbeddingStepType.OPENSEARCH_REINDEX:
                    self._reindex_opensearch(video_id, request, progress)

            except Exception as e:
                logger.error(
                    f"Failed to execute step {step.step_type.value} for video {video_id}: {e}",
                    exc_info=True
                )
                progress.errors.append({
                    "video_id": str(video_id),
                    "step": step.step_type.value,
                    "error": str(e),
                    "type": type(e).__name__,
                })

    def _regenerate_scene_text_embeddings(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Regenerate text embeddings for all scenes in a video"""
        scenes = self.db.get_scenes_for_video(video_id)
        progress.scenes_total += len(scenes)

        for scene in scenes:
            try:
                # Skip if embeddings exist and not forcing
                if not request.force and scene.embedding_transcript is not None:
                    progress.scenes_skipped += 1
                    continue

                # Regenerate using SidecarBuilder
                self.sidecar_builder._create_multi_channel_embeddings(scene)
                progress.scenes_processed += 1

            except Exception as e:
                logger.error(f"Failed to regenerate text embeddings for scene {scene.id}: {e}")
                progress.scenes_failed += 1

    def _regenerate_scene_clip_embeddings(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Regenerate CLIP embeddings for all scenes in a video"""
        if not self.clip_embedder or not self.settings.clip_enabled:
            logger.info("CLIP embeddings disabled, skipping")
            return

        scenes = self.db.get_scenes_for_video(video_id)

        for scene in scenes:
            try:
                # Skip if embedding exists and not forcing
                if not request.force and scene.embedding_visual_clip is not None:
                    continue

                # Regenerate using SidecarBuilder
                self.sidecar_builder._add_clip_embedding(scene)

            except Exception as e:
                logger.error(f"Failed to regenerate CLIP embedding for scene {scene.id}: {e}")

    def _regenerate_scene_person_embeddings(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Regenerate scene person embeddings from thumbnails"""
        if not self.clip_embedder or not self.settings.clip_enabled:
            logger.info("CLIP embeddings disabled, skipping scene person embeddings")
            return

        scenes = self.db.get_scenes_for_video(video_id)

        for scene in scenes:
            try:
                # Check if embedding exists
                existing = self.db.get_scene_person_embeddings(scene.id)
                if not request.force and existing:
                    continue

                # Generate thumbnail embedding
                thumbnail_path = self.storage.get_scene_thumbnail_path(video_id, scene.scene_number)

                if not thumbnail_path:
                    logger.warning(f"No thumbnail found for scene {scene.id}")
                    continue

                # Download thumbnail
                thumbnail_bytes = self.storage.download_file(thumbnail_path)

                # Generate embedding
                embedding = self.clip_embedder.create_visual_embedding(thumbnail_bytes)

                # Store in scene_person_embeddings
                self.db.upsert_scene_person_embedding(
                    scene_id=scene.id,
                    kind="thumbnail",
                    ordinal=0,
                    embedding=embedding,
                )

            except Exception as e:
                logger.error(f"Failed to regenerate scene person embedding for scene {scene.id}: {e}")

    def _regenerate_person_photo_embeddings(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Regenerate embeddings for person reference photos"""
        if not self.clip_embedder or not self.settings.clip_enabled:
            logger.info("CLIP embeddings disabled, skipping person photo embeddings")
            return

        # Get video to find owner_id
        video = self.db.get_video(video_id)
        if not video:
            return

        # Get all persons for owner
        persons = self.db.get_persons_for_owner(video.owner_id)

        for person in persons:
            # Get photos for person
            photos = self.db.get_person_photos(person.id)
            progress.person_photos_total += len(photos)

            for photo in photos:
                try:
                    # Skip if embedding exists and not forcing
                    if not request.force and photo.embedding is not None:
                        continue

                    # Regenerate using PersonPhotoProcessor
                    self.person_processor.process_photo(photo.id)
                    progress.person_photos_processed += 1

                except Exception as e:
                    logger.error(f"Failed to regenerate photo embedding for photo {photo.id}: {e}")
                    progress.person_photos_failed += 1

    def _regenerate_person_query_embeddings(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Recompute aggregated person query embeddings"""
        # Get video to find owner_id
        video = self.db.get_video(video_id)
        if not video:
            return

        # Get all persons for owner
        persons = self.db.get_persons_for_owner(video.owner_id)
        progress.persons_total = len(persons)

        for person in persons:
            try:
                # Get all READY photos
                photos = self.db.get_person_photos_ready(person.id)

                if not photos:
                    logger.info(f"No READY photos for person {person.id}")
                    continue

                # Compute mean embedding
                embeddings = [photo.embedding for photo in photos if photo.embedding]

                if not embeddings:
                    continue

                import numpy as np
                mean_embedding = np.mean(embeddings, axis=0)
                mean_embedding = mean_embedding / np.linalg.norm(mean_embedding)

                # Update person query_embedding
                self.db.update_person_query_embedding(person.id, mean_embedding.tolist())
                progress.persons_processed += 1

            except Exception as e:
                logger.error(f"Failed to regenerate query embedding for person {person.id}: {e}")
                progress.persons_failed += 1

    def _reindex_opensearch(
        self,
        video_id: UUID,
        request: ReprocessRequest,
        progress: ReprocessProgress,
    ) -> None:
        """Reindex scenes to OpenSearch"""
        if not self.opensearch:
            logger.info("OpenSearch disabled, skipping reindex")
            return

        scenes = self.db.get_scenes_for_video(video_id)

        for scene in scenes:
            try:
                # Reindex scene
                self.db.index_scene_to_opensearch(scene)

            except Exception as e:
                logger.error(f"Failed to reindex scene {scene.id} to OpenSearch: {e}")
