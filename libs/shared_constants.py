"""
Shared constants across Heimdex services.

This module contains constants that need to be shared between
API and Worker services without creating circular dependencies.
"""

# Embedding reprocessing spec version
# Update this whenever embedding generation logic changes
LATEST_EMBEDDING_SPEC_VERSION = "2026-01-06"
