"""OpenAI client adapter for worker."""
import base64
import json
import logging
from pathlib import Path
from typing import Optional
from openai import OpenAI

from ..config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client wrapper."""

    def __init__(self):
        """Initialize the OpenAI client."""
        self.client = OpenAI(api_key=settings.openai_api_key)

    def transcribe_audio(self, audio_file_path: Path) -> str:
        """
        Transcribe audio using Whisper.

        Args:
            audio_file_path: Path to audio file

        Returns:
            str: Transcription text
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
            str: Visual summary text
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

    def analyze_scene_visuals_optimized(
        self,
        image_path: Path,
        transcript_segment: Optional[str] = None,
        language: str = "ko",
    ) -> Optional[dict]:
        """
        Analyze scene visuals using strict JSON schema for token efficiency.

        This method uses a stricter prompt that:
        - Returns structured JSON only (no apologies or free-form text)
        - Uses minimal tokens
        - Can return "no_content" status for uninformative scenes

        Args:
            image_path: Path to single best keyframe
            transcript_segment: Optional transcript segment for context
            language: Language for the summary ('ko' or 'en')

        Returns:
            Optional[dict]: Dict with structure:
            {
                "status": "ok" | "no_content",
                "description": "short Korean/English description",
                "main_entities": ["entity1", "entity2"],  # if enabled
                "actions": ["action1", "action2"],  # if enabled
                "confidence": 0.0-1.0
            }
            Returns None if API call fails.
        """
        logger.info(f"Analyzing keyframe with optimized prompt in language: {language}")

        try:
            # Encode image to base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")

            # Build strict system prompt with richer descriptions
            system_prompts = {
                "ko": """당신은 비디오 장면 분석 전문가입니다. 다음 JSON 스키마로만 응답하세요:

{
  "status": "ok" 또는 "no_content",
  "description": "1-2문장의 구체적이고 설명적인 한국어 장면 묘사 (최대 200자)",
  "main_entities": ["주요 인물, 사물, 장소 등의 짧은 명사구"],
  "actions": ["발생하는 행동을 나타내는 짧은 동사구"],
  "confidence": 0.0에서 1.0 사이의 숫자
}

규칙:
- 장면이 완전히 검은색, 너무 흐릿하거나 인식할 수 없는 경우: status="no_content", description="", main_entities=[], actions=[], confidence=0.0
- 그 외의 경우: status="ok"
- description: 누가 무엇을 하고 있는지, 장소와 분위기를 포함한 1-2문장의 구체적 설명 (최대 200자)
- main_entities: 주요 등장 인물, 물체, 장소를 짧은 명사구로 나열 (각 항목은 30자 미만)
- actions: 일어나는 행동을 짧은 동사구로 나열 (각 항목은 30자 미만)
- 태그로 사용 가능하도록 entities와 actions는 간결하게
- JSON만 출력하고 추가 설명 없음""",
                "en": """You are a video scene analysis expert. Respond ONLY with this JSON schema:

{
  "status": "ok" or "no_content",
  "description": "1-2 descriptive sentences about the scene (max 200 characters)",
  "main_entities": ["short noun phrases for people, objects, locations"],
  "actions": ["short verb phrases for actions happening"],
  "confidence": number between 0.0 and 1.0
}

Rules:
- If scene is completely black, too blurry, or nothing recognizable: status="no_content", description="", main_entities=[], actions=[], confidence=0.0
- Otherwise: status="ok"
- description: 1-2 specific sentences describing who/what is present, what's happening, location and mood (max 200 chars)
- main_entities: short noun phrases for main people, objects, locations (each item under 30 chars)
- actions: short verb phrases for actions occurring (each item under 30 chars)
- Keep entities and actions concise for use as clickable tags
- Output JSON only, no additional text""",
            }

            system_prompt = system_prompts.get(language, system_prompts["ko"])

            # Optionally remove entities/actions from schema if disabled
            if not settings.visual_semantics_include_entities:
                system_prompt = system_prompt.replace(
                    '"main_entities": ["짧은 명사구 목록"],\n  ',
                    ""
                ).replace(
                    '"main_entities": ["short noun phrases"],\n  ',
                    ""
                )
            if not settings.visual_semantics_include_actions:
                system_prompt = system_prompt.replace(
                    '"actions": ["짧은 동사구 목록"],\n  ',
                    ""
                ).replace(
                    '"actions": ["short verb phrases"],\n  ',
                    ""
                )

            # Build user message
            user_prompts = {
                "ko": "이 비디오 장면을 분석하고 JSON으로 응답하세요.",
                "en": "Analyze this video scene and respond with JSON.",
            }
            user_message = user_prompts.get(language, user_prompts["ko"])

            # Add transcript context if available
            if transcript_segment and transcript_segment.strip():
                transcript_preview = transcript_segment[:200]  # Limit transcript length
                if language == "ko":
                    user_message += f"\n\n대본: {transcript_preview}"
                else:
                    user_message += f"\n\nTranscript: {transcript_preview}"

            # Create messages
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "low",  # Use low detail for cost efficiency
                            }
                        },
                    ]
                }
            ]

            # Call OpenAI with optimized settings
            response = self.client.chat.completions.create(
                model=settings.visual_semantics_model,
                messages=messages,
                max_tokens=settings.visual_semantics_max_tokens,
                temperature=settings.visual_semantics_temperature,
                response_format={"type": "json_object"},  # Force JSON response
            )

            # Parse JSON response
            response_text = response.choices[0].message.content
            result = json.loads(response_text)

            # Log result
            if result.get("status") == "no_content":
                logger.info("Visual analysis: no_content (scene not informative)")
            else:
                logger.info(f"Visual analysis: {result.get('description', '')[:50]}...")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}", exc_info=True)
            return None

    def summarize_video_from_scenes(
        self,
        scene_descriptions: list[str],
        transcript_language: str = "ko",
    ) -> Optional[str]:
        """
        Generate video-level summary from scene descriptions.

        Token efficiency:
        - Limits number of scene descriptions to avoid token overflow
        - Truncates combined text if needed
        - Uses small max_tokens for concise output
        - Requests 3-5 sentences max

        Args:
            scene_descriptions: List of scene descriptions (in order)
            transcript_language: Language for the summary ('ko' or 'en')

        Returns:
            Optional[str]: Video summary (3-5 sentences) or None if failed
        """
        if not scene_descriptions:
            logger.warning("No scene descriptions provided for video summary")
            return None

        try:
            # Limit number of scenes to manage token usage
            # Take first N, some from middle, and last few for representative sample
            max_scenes = 30
            if len(scene_descriptions) > max_scenes:
                # Take first 10, middle 10, last 10
                sampled = (
                    scene_descriptions[:10]
                    + scene_descriptions[len(scene_descriptions)//2 - 5:len(scene_descriptions)//2 + 5]
                    + scene_descriptions[-10:]
                )
                logger.info(f"Sampled {len(sampled)} scenes from {len(scene_descriptions)} total for summary")
            else:
                sampled = scene_descriptions

            # Combine scene descriptions
            combined_text = "\n".join(f"장면 {i+1}: {desc}" if transcript_language == "ko" else f"Scene {i+1}: {desc}"
                                     for i, desc in enumerate(sampled))

            # Truncate if too long (preserve ~4000 characters for safety)
            max_chars = 4000
            if len(combined_text) > max_chars:
                combined_text = combined_text[:max_chars] + "..."
                logger.info(f"Truncated scene descriptions to {max_chars} characters")

            # Build system prompt
            system_prompts = {
                "ko": """당신은 비디오 요약 전문가입니다. 장면별 설명을 바탕으로 전체 비디오를 요약하세요.

요구사항:
- 3-5문장의 간결한 한국어 요약 작성
- 비디오의 주요 내용, 주제, 흐름을 포착
- 구체적이고 설명적으로 작성
- 단락 형식 또는 3-5개의 핵심 포인트
- 추가 설명 없이 요약만 제공""",
                "en": """You are a video summarization expert. Summarize the entire video based on scene descriptions.

Requirements:
- Write a concise 3-5 sentence summary in English
- Capture the main content, themes, and flow of the video
- Be specific and descriptive
- Format as a paragraph or 3-5 key points
- Provide only the summary without additional commentary""",
            }

            system_prompt = system_prompts.get(transcript_language, system_prompts["ko"])

            # User message with scene descriptions
            user_message = combined_text

            # Call OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use cost-efficient model for summaries
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=300,  # Limit output length
                temperature=0.3,  # Slightly creative but mostly deterministic
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated video summary: {summary[:100]}...")
            return summary

        except Exception as e:
            logger.error(f"Failed to generate video summary: {e}", exc_info=True)
            return None

    def create_embedding(self, text: str) -> list[float]:
        """
        Create embedding for given text.

        Args:
            text: Text to embed

        Returns:
            list[float]: List of floats representing the embedding vector
        """
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimensions,
        )
        return response.data[0].embedding


# Global OpenAI client instance
openai_client = OpenAIClient()
