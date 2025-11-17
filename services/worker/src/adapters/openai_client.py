"""OpenAI client adapter for worker."""
import base64
import logging
from pathlib import Path
from typing import Optional
from openai import OpenAI

from ..config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client wrapper."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def transcribe_audio(self, audio_file_path: Path) -> str:
        """
        Transcribe audio using Whisper.

        Args:
            audio_file_path: Path to audio file

        Returns:
            Transcription text
        """
        logger.info(f"Transcribing audio from {audio_file_path}")
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
            )
        logger.info(f"Transcription complete: {len(transcript)} chars")
        return transcript

    def analyze_scene_visuals(
        self,
        image_paths: list[Path],
        transcript_segment: Optional[str] = None,
        language: str = "ko",
    ) -> str:
        """
        Analyze scene visuals using GPT-4o with images.

        Args:
            image_paths: List of paths to keyframe images
            transcript_segment: Optional transcript segment for context
            language: Language for the summary ('ko' or 'en')

        Returns:
            Visual summary text
        """
        logger.info(f"Analyzing {len(image_paths)} keyframes with GPT-4o in language: {language}")

        # Encode images to base64
        image_contents = []
        for image_path in image_paths:
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")
                image_contents.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}",
                        "detail": "low",  # Use low detail for faster/cheaper processing
                    }
                })

        # Build prompt based on language
        prompts = {
            "ko": "이 비디오 장면에서 무슨 일이 일어나고 있는지 1-2문장으로 간결하게 설명하세요. 주요 주제, 행동 및 시각적 요소에 중점을 두세요.",
            "en": "Describe what is happening in this video scene in 1-2 concise sentences. Focus on the main subjects, actions, and visual elements.",
        }
        prompt = prompts.get(language, prompts["ko"])  # Default to Korean

        if transcript_segment:
            if language == "ko":
                prompt += f"\n\n대본 컨텍스트: {transcript_segment}"
            else:
                prompt += f"\n\nTranscript context: {transcript_segment}"

        # Create messages
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_contents,
                ]
            }
        ]

        # Call GPT-4o
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
        )

        visual_summary = response.choices[0].message.content
        logger.info(f"Visual analysis complete: {visual_summary}")
        return visual_summary

    def create_embedding(self, text: str) -> list[float]:
        """
        Create embedding for given text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimensions,
        )
        return response.data[0].embedding


# Global OpenAI client instance
openai_client = OpenAIClient()
