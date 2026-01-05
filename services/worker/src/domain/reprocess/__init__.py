"""Reprocessing domain module"""

import sys
from pathlib import Path

# Add libs to path for shared constants
libs_path = Path(__file__).resolve().parents[5] / "libs"
if str(libs_path) not in sys.path:
    sys.path.insert(0, str(libs_path))

from shared_constants import LATEST_EMBEDDING_SPEC_VERSION

from .latest_reprocess import (
    ReprocessScope,
    EmbeddingStepType,
    ReprocessSpec,
    ReprocessRequest,
    ReprocessProgress,
    ReprocessRunner,
)

__all__ = [
    "LATEST_EMBEDDING_SPEC_VERSION",
    "ReprocessScope",
    "EmbeddingStepType",
    "ReprocessSpec",
    "ReprocessRequest",
    "ReprocessProgress",
    "ReprocessRunner",
]
