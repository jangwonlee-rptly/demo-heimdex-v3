"""Custom exception hierarchy for Heimdex API.

This module defines a structured exception hierarchy that makes error handling
more explicit and enables better error reporting to clients.

Exception Hierarchy:
    HeimdexException (base)
    ├── ResourceNotFoundException
    │   ├── VideoNotFoundException
    │   └── SceneNotFoundException
    ├── AuthorizationException
    │   ├── UnauthorizedException
    │   └── ForbiddenException
    ├── ValidationException
    │   ├── InvalidInputException
    │   └── InvalidFileException
    ├── ExternalServiceException
    │   ├── DatabaseException
    │   ├── StorageException
    │   ├── QueueException
    │   └── OpenAIException
    └── ProcessingException
        ├── TranscriptionException
        ├── SceneDetectionException
        └── EmbeddingException
"""


class HeimdexException(Exception):
    """Base exception for all Heimdex errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code for API responses
        status_code: HTTP status code to return
        details: Optional additional context
    """

    def __init__(
        self,
        message: str,
        error_code: str = "HEIMDEX_ERROR",
        status_code: int = 500,
        details: dict | None = None,
    ):
        """Initialize HeimdexException.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            status_code: HTTP status code to return
            details: Optional additional context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


# ============================================================================
# Resource Not Found Exceptions (404)
# ============================================================================


class ResourceNotFoundException(HeimdexException):
    """Base exception for resource not found errors."""

    def __init__(self, message: str, error_code: str = "RESOURCE_NOT_FOUND", details: dict | None = None):
        """Initialize ResourceNotFoundException."""
        super().__init__(message, error_code, status_code=404, details=details)


class VideoNotFoundException(ResourceNotFoundException):
    """Raised when a video is not found in the database."""

    def __init__(self, video_id: str, details: dict | None = None):
        """Initialize VideoNotFoundException.

        Args:
            video_id: The UUID of the video that was not found
            details: Optional additional context
        """
        message = f"Video {video_id} not found"
        super().__init__(message, error_code="VIDEO_NOT_FOUND", details=details)
        self.video_id = video_id


class SceneNotFoundException(ResourceNotFoundException):
    """Raised when a scene is not found in the database."""

    def __init__(self, scene_id: str, details: dict | None = None):
        """Initialize SceneNotFoundException.

        Args:
            scene_id: The UUID of the scene that was not found
            details: Optional additional context
        """
        message = f"Scene {scene_id} not found"
        super().__init__(message, error_code="SCENE_NOT_FOUND", details=details)
        self.scene_id = scene_id


class UserProfileNotFoundException(ResourceNotFoundException):
    """Raised when a user profile is not found in the database."""

    def __init__(self, user_id: str, details: dict | None = None):
        """Initialize UserProfileNotFoundException.

        Args:
            user_id: The UUID of the user whose profile was not found
            details: Optional additional context
        """
        message = f"User profile for {user_id} not found"
        super().__init__(message, error_code="USER_PROFILE_NOT_FOUND", details=details)
        self.user_id = user_id


# ============================================================================
# Authorization Exceptions (401, 403)
# ============================================================================


class AuthorizationException(HeimdexException):
    """Base exception for authorization errors."""

    def __init__(self, message: str, error_code: str = "AUTHORIZATION_ERROR", status_code: int = 403, details: dict | None = None):
        """Initialize AuthorizationException."""
        super().__init__(message, error_code, status_code, details)


class UnauthorizedException(AuthorizationException):
    """Raised when authentication is missing or invalid."""

    def __init__(self, message: str = "Authentication required", details: dict | None = None):
        """Initialize UnauthorizedException."""
        super().__init__(message, error_code="UNAUTHORIZED", status_code=401, details=details)


class ForbiddenException(AuthorizationException):
    """Raised when user is authenticated but not authorized."""

    def __init__(self, message: str = "Access forbidden", details: dict | None = None):
        """Initialize ForbiddenException."""
        super().__init__(message, error_code="FORBIDDEN", status_code=403, details=details)


# ============================================================================
# Validation Exceptions (400, 422)
# ============================================================================


class ValidationException(HeimdexException):
    """Base exception for validation errors."""

    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", details: dict | None = None):
        """Initialize ValidationException."""
        super().__init__(message, error_code, status_code=422, details=details)


class InvalidInputException(ValidationException):
    """Raised when request input is invalid."""

    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        """Initialize InvalidInputException.

        Args:
            message: Error message
            field: Name of the invalid field
            details: Optional additional context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message, error_code="INVALID_INPUT", details=error_details)


class InvalidFileException(ValidationException):
    """Raised when uploaded file is invalid."""

    def __init__(self, message: str, filename: str | None = None, details: dict | None = None):
        """Initialize InvalidFileException.

        Args:
            message: Error message
            filename: Name of the invalid file
            details: Optional additional context
        """
        error_details = details or {}
        if filename:
            error_details["filename"] = filename
        super().__init__(message, error_code="INVALID_FILE", details=error_details)


# ============================================================================
# External Service Exceptions (502, 503)
# ============================================================================


class ExternalServiceException(HeimdexException):
    """Base exception for external service errors."""

    def __init__(self, message: str, error_code: str = "EXTERNAL_SERVICE_ERROR", details: dict | None = None):
        """Initialize ExternalServiceException."""
        super().__init__(message, error_code, status_code=503, details=details)


class DatabaseException(ExternalServiceException):
    """Raised when database operation fails."""

    def __init__(self, message: str, operation: str | None = None, details: dict | None = None):
        """Initialize DatabaseException.

        Args:
            message: Error message
            operation: Database operation that failed (e.g., "insert", "query")
            details: Optional additional context
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(message, error_code="DATABASE_ERROR", details=error_details)


class StorageException(ExternalServiceException):
    """Raised when storage operation fails."""

    def __init__(self, message: str, operation: str | None = None, path: str | None = None, details: dict | None = None):
        """Initialize StorageException.

        Args:
            message: Error message
            operation: Storage operation that failed (e.g., "upload", "download")
            path: Storage path involved
            details: Optional additional context
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if path:
            error_details["path"] = path
        super().__init__(message, error_code="STORAGE_ERROR", details=error_details)


class QueueException(ExternalServiceException):
    """Raised when message queue operation fails."""

    def __init__(self, message: str, queue: str | None = None, details: dict | None = None):
        """Initialize QueueException.

        Args:
            message: Error message
            queue: Name of the queue
            details: Optional additional context
        """
        error_details = details or {}
        if queue:
            error_details["queue"] = queue
        super().__init__(message, error_code="QUEUE_ERROR", details=error_details)


class OpenAIException(ExternalServiceException):
    """Raised when OpenAI API operation fails."""

    def __init__(self, message: str, operation: str | None = None, details: dict | None = None):
        """Initialize OpenAIException.

        Args:
            message: Error message
            operation: OpenAI operation that failed (e.g., "embedding", "transcription")
            details: Optional additional context
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(message, error_code="OPENAI_ERROR", details=error_details)


# ============================================================================
# Processing Exceptions (500)
# ============================================================================


class ProcessingException(HeimdexException):
    """Base exception for processing errors."""

    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR", details: dict | None = None):
        """Initialize ProcessingException."""
        super().__init__(message, error_code, status_code=500, details=details)


class TranscriptionException(ProcessingException):
    """Raised when audio transcription fails."""

    def __init__(self, message: str, video_id: str | None = None, details: dict | None = None):
        """Initialize TranscriptionException.

        Args:
            message: Error message
            video_id: UUID of the video being transcribed
            details: Optional additional context
        """
        error_details = details or {}
        if video_id:
            error_details["video_id"] = video_id
        super().__init__(message, error_code="TRANSCRIPTION_ERROR", details=error_details)


class SceneDetectionException(ProcessingException):
    """Raised when scene detection fails."""

    def __init__(self, message: str, video_id: str | None = None, detector: str | None = None, details: dict | None = None):
        """Initialize SceneDetectionException.

        Args:
            message: Error message
            video_id: UUID of the video being processed
            detector: Name of the detector that failed
            details: Optional additional context
        """
        error_details = details or {}
        if video_id:
            error_details["video_id"] = video_id
        if detector:
            error_details["detector"] = detector
        super().__init__(message, error_code="SCENE_DETECTION_ERROR", details=error_details)


class EmbeddingException(ProcessingException):
    """Raised when embedding generation fails."""

    def __init__(self, message: str, text_length: int | None = None, details: dict | None = None):
        """Initialize EmbeddingException.

        Args:
            message: Error message
            text_length: Length of text that failed to embed
            details: Optional additional context
        """
        error_details = details or {}
        if text_length is not None:
            error_details["text_length"] = text_length
        super().__init__(message, error_code="EMBEDDING_ERROR", details=error_details)


# ============================================================================
# Conflict Exceptions (409)
# ============================================================================


class ConflictException(HeimdexException):
    """Raised when operation conflicts with current state."""

    def __init__(self, message: str, resource_type: str | None = None, details: dict | None = None):
        """Initialize ConflictException.

        Args:
            message: Error message
            resource_type: Type of resource in conflict
            details: Optional additional context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        super().__init__(message, error_code="CONFLICT", status_code=409, details=error_details)


# ============================================================================
# Export-Related Exceptions
# ============================================================================


class ExportLimitExceededException(HeimdexException):
    """Raised when user exceeds daily export limit."""

    def __init__(
        self,
        message: str = "Daily export limit reached",
        current_count: int | None = None,
        limit: int = 10,
        hours_until_reset: int | None = None,
        details: dict | None = None,
    ):
        """Initialize ExportLimitExceededException.

        Args:
            message: Error message
            current_count: Current number of exports today
            limit: Daily export limit
            hours_until_reset: Hours until limit resets
            details: Optional additional context
        """
        error_details = details or {}
        error_details["limit"] = limit
        if current_count is not None:
            error_details["current_count"] = current_count
        if hours_until_reset is not None:
            error_details["hours_until_reset"] = hours_until_reset

        super().__init__(
            message,
            error_code="EXPORT_LIMIT_EXCEEDED",
            status_code=429,
            details=error_details,
        )


class ExportExpiredException(ResourceNotFoundException):
    """Raised when trying to access an expired export."""

    def __init__(self, export_id: str, details: dict | None = None):
        """Initialize ExportExpiredException.

        Args:
            export_id: ID of the expired export
            details: Optional additional context
        """
        message = f"Export {export_id} has expired (24-hour limit). Please create a new export."
        super().__init__(message, error_code="EXPORT_EXPIRED", details=details)
        self.export_id = export_id


class SceneTooLongException(ValidationException):
    """Raised when scene duration exceeds YouTube Shorts limit."""

    def __init__(
        self,
        scene_duration_s: float,
        max_duration_s: int = 180,
        details: dict | None = None,
    ):
        """Initialize SceneTooLongException.

        Args:
            scene_duration_s: Duration of the scene in seconds
            max_duration_s: Maximum allowed duration (default: 180s)
            details: Optional additional context
        """
        message = f"Scene duration ({scene_duration_s:.1f}s) exceeds YouTube Shorts maximum ({max_duration_s}s)"
        error_details = details or {}
        error_details["scene_duration_s"] = scene_duration_s
        error_details["max_duration_s"] = max_duration_s

        super().__init__(message, error_code="SCENE_TOO_LONG", details=error_details)
        self.scene_duration_s = scene_duration_s
        self.max_duration_s = max_duration_s
