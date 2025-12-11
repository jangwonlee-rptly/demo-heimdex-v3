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

    def transcribe_audio(self, audio_file_path: Path, language: str = None) -> str:
        """
        Transcribe audio using Whisper.

        Args:
            audio_file_path: Path to audio file
            language: Optional ISO-639-1 language code (e.g., 'ko', 'en', 'ja', 'ru').
                     If not provided, Whisper will auto-detect the language.

        Returns:
            str: Transcription text
        """
        if language:
            logger.info(f"Transcribing audio from {audio_file_path} with language hint: {language}")
        else:
            logger.info(f"Transcribing audio from {audio_file_path} (auto-detect language)")

        with open(audio_file_path, "rb") as audio_file:
            params = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "text",
            }
            # Only add language if explicitly specified
            if language:
                params["language"] = language

            transcript = self.client.audio.transcriptions.create(**params)

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

        # Call GPT-5-nano
        # Note: newer models require max_completion_tokens instead of max_tokens
        response = self.client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            max_completion_tokens=150,
        )

        visual_summary = response.choices[0].message.content
        logger.info(f"Visual analysis complete: {visual_summary}")
        return visual_summary

    def analyze_scene_visuals_optimized(
        self,
        image_path: Path,
        language: str = "ko",
    ) -> Optional[dict]:
        """
        Analyze scene visuals using strict JSON schema with detailed descriptions.

        This method focuses purely on visual content without relying on transcripts:
        - Returns structured JSON only (no apologies or free-form text)
        - Provides detailed visual descriptions of all significant elements
        - Can return "no_content" status for uninformative scenes (black/blurred only)

        Args:
            image_path: Path to single best keyframe
            language: Language for the summary ('ko' or 'en')

        Returns:
            Optional[dict]: Dict with structure:
            {
                "status": "ok" | "no_content",
                "description": "detailed visual description (max 500 chars)",
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

            # Build strict system prompt with detailed visual descriptions
            # NOTE: Visual analysis should be completely independent of transcripts
            system_prompts = {
                "ko": """당신은 비디오 장면의 시각적 내용을 상세히 분석하는 전문가입니다. 다음 JSON 스키마로만 응답하세요:

{
  "status": "ok" 또는 "no_content",
  "description": "장면의 모든 중요한 시각적 세부사항을 설명하는 상세한 한국어 묘사 (최대 500자)",
  "main_entities": ["보이는 모든 인물, 사물, 장소, 텍스트 등의 명사구"],
  "actions": ["관찰되는 모든 행동, 동작, 상태를 나타내는 동사구"],
  "confidence": 0.0에서 1.0 사이의 숫자
}

중요 규칙:
- **시각적 내용에만 집중**: 화면에 보이는 것만 설명하세요. 음성이나 대본은 무시하세요.
- **status="no_content"**: 완전히 검은 화면이나 완전히 흐릿한 경우에만 사용
- **상세한 설명 필수**: status="ok"인 경우 반드시 모든 필드를 상세히 채우세요

description 작성 가이드 (최대 500자):
1. 전체 장면 구성: 실내/외, 배경, 조명, 색감, 분위기
2. 주요 대상: 사람(외모, 복장, 표정), 물체(크기, 색상, 위치), 텍스트(내용, 스타일)
3. 행동/상태: 무엇을 하고 있는지, 움직임, 상호작용
4. 공간/레이아웃: 화면 구도, 카메라 앵글, 원근감
5. 눈에 띄는 세부사항: 브랜드, 로고, 특이한 요소

main_entities 작성:
- 화면에 보이는 모든 중요한 대상을 나열
- 예: "파란색 셔츠 입은 남성", "노트북", "흰색 배경", "회사 로고", "창문"
- 각 항목은 구체적이고 서술적으로 (최대 40자)

actions 작성:
- 관찰되는 모든 행동과 상태를 나열
- 정적 장면도 "표시됨", "놓여있음", "비춰짐" 등으로 표현
- 예: "키보드 타이핑", "화면 가리킴", "웃음", "텍스트 표시됨"
- 각 항목은 동사구로 (최대 40자)

불확실한 경우:
- 추측하지 말고 보이는 것만 설명
- 불확실하면 confidence를 낮게 설정 (0.3-0.7)
- 그래도 최대한 상세히 설명 시도

JSON만 출력하고 추가 설명 없음.""",
                "en": """You are an expert at analyzing detailed visual content in video scenes. Respond ONLY with this JSON schema:

{
  "status": "ok" or "no_content",
  "description": "Detailed description of all significant visual details in the scene (max 500 characters)",
  "main_entities": ["noun phrases for ALL visible people, objects, locations, text, etc."],
  "actions": ["verb phrases for ALL observed actions, movements, states"],
  "confidence": number between 0.0 and 1.0
}

Critical Rules:
- **FOCUS ON VISUALS ONLY**: Describe only what you SEE on screen. Ignore audio/transcripts.
- **status="no_content"**: Use ONLY for completely black screens or completely blurred content
- **DETAILED DESCRIPTIONS REQUIRED**: If status="ok", you MUST fill all fields thoroughly

description guidelines (max 500 chars):
1. Overall scene composition: indoor/outdoor, background, lighting, colors, atmosphere
2. Main subjects: people (appearance, clothing, expressions), objects (size, color, position), text (content, style)
3. Actions/states: what is happening, movements, interactions
4. Space/layout: screen composition, camera angle, perspective
5. Notable details: brands, logos, unique elements

main_entities guidelines:
- List ALL significant visible subjects
- Examples: "man in blue shirt", "laptop computer", "white background", "company logo", "window"
- Each item should be specific and descriptive (max 40 chars)

actions guidelines:
- List ALL observed actions and states
- For static scenes use "displayed", "positioned", "shown", etc.
- Examples: "typing on keyboard", "pointing at screen", "smiling", "text displayed"
- Each item as verb phrase (max 40 chars)

When uncertain:
- Don't guess - describe only what you see
- Use lower confidence if unsure (0.3-0.7)
- Still attempt maximum detail

Output JSON only, no additional text.""",
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

            # Build user message (DO NOT include transcript - visual analysis should be independent)
            user_prompts = {
                "ko": "이 비디오 장면의 시각적 내용을 상세히 분석하고 JSON으로 응답하세요. 화면에 보이는 모든 중요한 세부사항을 포함하세요.",
                "en": "Analyze the visual content of this video scene in detail and respond with JSON. Include all significant visual details you can see on screen.",
            }
            user_message = user_prompts.get(language, user_prompts["ko"])

            # NOTE: Intentionally NOT including transcript_segment here
            # Visual analysis should be completely independent of audio/transcripts
            # to provide pure visual descriptions

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
            # Note: newer models (gpt-4o, gpt-5-nano, etc.) require max_completion_tokens instead of max_tokens
            # Note: gpt-5-nano only supports default temperature (1.0), so we omit it for that model
            api_params = {
                "model": settings.visual_semantics_model,
                "messages": messages,
                "max_completion_tokens": settings.visual_semantics_max_tokens,
                "response_format": {"type": "json_object"},  # Force JSON response
            }
            # Only add temperature if model supports it (gpt-5-nano does not)
            if "gpt-5-nano" not in settings.visual_semantics_model:
                api_params["temperature"] = settings.visual_semantics_temperature

            response = self.client.chat.completions.create(**api_params)

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
            # Note: newer models require max_completion_tokens instead of max_tokens
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use cost-efficient model for summaries
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_completion_tokens=300,  # Limit output length
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
