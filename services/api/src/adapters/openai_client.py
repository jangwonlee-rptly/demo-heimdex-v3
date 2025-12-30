"""OpenAI client adapter."""
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client wrapper."""

    def __init__(self, api_key: str):
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key for authentication
        """
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536

    def create_embedding(self, text: str) -> list[float]:
        """
        Create embedding for given text.

        Args:
            text: Text to embed

        Returns:
            list[float]: List of floats representing the embedding vector
        """
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            dimensions=self.embedding_dimensions,
        )
        return response.data[0].embedding


# DEPRECATED: Global instance removed for Phase 1 refactor.
# Use dependency injection instead via get_openai() from dependencies.py
openai_client: OpenAIClient = None  # type: ignore
