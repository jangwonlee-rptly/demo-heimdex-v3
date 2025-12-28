"""Visual intent router for automatic CLIP mode selection.

Determines whether a search query has visual intent (objects, actions, appearance)
or speech/text intent (dialogue, mentions, quotes) and adjusts search strategy accordingly.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Visual intent keywords (objects, actions, attributes)
VISUAL_OBJECTS = {
    # Common objects
    "person", "people", "man", "woman", "child", "face", "hand", "body",
    "car", "vehicle", "truck", "bus", "bike", "motorcycle",
    "building", "house", "room", "door", "window", "wall",
    "sign", "logo", "text", "banner", "poster",
    "food", "plate", "cup", "bottle", "table", "chair",
    "tree", "flower", "sky", "water", "mountain", "landscape",
    "animal", "dog", "cat", "bird", "horse",
    "phone", "computer", "screen", "camera", "book",
    "clothes", "shirt", "dress", "hat", "shoes",
    "crowd", "group", "audience", "meeting",

    # Korean food terms (visual objects)
    "떡볶이", "tteokbokki", "김치", "kimchi", "비빔밥", "bibimbap",
    "불고기", "bulgogi", "삼겹살", "samgyeopsal", "치킨", "chicken",
}

VISUAL_ACTIONS = {
    "walking", "running", "sitting", "standing", "jumping", "dancing",
    "talking", "speaking", "laughing", "crying", "smiling", "frowning",
    "eating", "drinking", "cooking", "working", "playing",
    "driving", "riding", "flying", "swimming", "climbing",
    "opening", "closing", "pointing", "waving", "holding",
    "looking", "watching", "staring", "gazing", "glancing",
    "moving", "entering", "leaving", "arriving", "departing",
    "fighting", "hugging", "kissing", "shaking", "clapping",
}

VISUAL_ATTRIBUTES = {
    # Colors
    "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown",
    "black", "white", "gray", "grey", "colorful", "bright", "dark",

    # Visual qualities
    "blurry", "sharp", "clear", "foggy", "bright", "dim", "shadowy",
    "close-up", "closeup", "wide", "zoomed", "zoom", "pan", "tilt",
    "indoor", "outdoor", "day", "night", "sunset", "sunrise",
    "big", "small", "large", "tiny", "huge", "massive",
    "beautiful", "ugly", "pretty", "handsome", "attractive",

    # Camera/shot descriptions
    "shot", "angle", "view", "scene", "frame", "background", "foreground",
}

VISUAL_PHRASES = {
    "what does it look like",
    "show me scenes with",
    "show me",
    "find scenes with",
    "scenes where",
    "video of",
    "footage of",
    "clip of",
    "appearance of",
    "looks like",
    "wearing",
    "dressed in",
    "in the background",
    "in the foreground",
}

# Speech/text intent keywords (dialogue, transcription)
SPEECH_KEYWORDS = {
    "says", "said", "mentions", "mentioned", "talks about", "talked about",
    "discusses", "discussed", "explains", "explained",
    "quote", "quotes", "line", "dialogue", "conversation",
    "tells", "told", "asks", "asked", "answers", "answered",
    "announces", "announced", "declares", "declared",
    "words", "phrase", "sentence", "spoken", "verbal",
}

SPEECH_PHRASES = {
    "he says",
    "she says",
    "they say",
    "the line where",
    "when he says",
    "when she says",
    "the part where",
    "the quote",
    "what they said",
    "what he said",
    "what she said",
}


@dataclass
class VisualIntentResult:
    """Result of visual intent analysis."""

    has_visual_intent: bool  # True if query suggests visual search
    has_speech_intent: bool  # True if query suggests speech/text search
    confidence: float  # Confidence in classification (0.0-1.0)
    matched_visual_terms: list[str]  # Visual keywords found in query
    matched_speech_terms: list[str]  # Speech keywords found in query
    suggested_mode: str  # "recall", "rerank", or "skip"
    suggested_weight_adjustment: Optional[float]  # Adjustment to visual weight (-1.0 to +1.0)
    explanation: str  # Human-readable explanation


class VisualIntentRouter:
    """Heuristic router to determine if a query has visual intent.

    Analyzes query text to decide whether CLIP visual search should be:
    - Enabled with high weight (strong visual intent)
    - Enabled with low weight (weak visual intent)
    - Disabled (no visual intent, speech/text only)

    Uses keyword matching and pattern detection. Deterministic and logged.
    """

    def __init__(self):
        """Initialize the router."""
        # Precompile regex patterns for efficiency
        self._quote_pattern = re.compile(r'[""\'"]')
        self._question_pattern = re.compile(
            r'^(what|who|when|where|why|how|which|whose|whom)\s+',
            re.IGNORECASE
        )

    def analyze(self, query: str) -> VisualIntentResult:
        """Analyze query to determine visual intent.

        Args:
            query: User's search query text

        Returns:
            VisualIntentResult with classification and suggestions
        """
        if not query or not query.strip():
            return VisualIntentResult(
                has_visual_intent=False,
                has_speech_intent=False,
                confidence=0.0,
                matched_visual_terms=[],
                matched_speech_terms=[],
                suggested_mode="skip",
                suggested_weight_adjustment=None,
                explanation="Empty query",
            )

        query_lower = query.lower()
        query_normalized = self._normalize_query(query_lower)

        # Detect visual and speech signals
        visual_terms = self._match_visual_terms(query_lower, query_normalized)
        speech_terms = self._match_speech_terms(query_lower, query_normalized)

        # Check for quotes (strong speech signal)
        has_quotes = bool(self._quote_pattern.search(query))
        if has_quotes:
            speech_terms.append("contains_quotes")

        # Check for long question pattern (likely speech/meaning search)
        is_long_question = (
            len(query.split()) > 6
            and self._question_pattern.match(query)
        )
        if is_long_question:
            speech_terms.append("long_question")

        # Compute signals
        visual_score = len(visual_terms)
        speech_score = len(speech_terms)

        # Classify intent
        has_visual_intent = visual_score > 0
        has_speech_intent = speech_score > 0

        # Determine mode and weight adjustment
        if visual_score >= 3 and speech_score == 0:
            # Strong visual signal, no speech signal
            suggested_mode = "recall"
            suggested_weight_adjustment = 0.15  # Boost visual weight
            confidence = 0.9
            explanation = f"Strong visual intent: {', '.join(visual_terms[:3])}"

        elif visual_score >= 2 and speech_score <= 1:
            # Moderate visual signal
            suggested_mode = "rerank"
            suggested_weight_adjustment = 0.05  # Slight boost
            confidence = 0.7
            explanation = f"Moderate visual intent: {', '.join(visual_terms)}"

        elif visual_score >= 1 and speech_score == 0:
            # Weak visual signal
            suggested_mode = "rerank"
            suggested_weight_adjustment = 0.0  # No adjustment
            confidence = 0.5
            explanation = f"Weak visual intent: {', '.join(visual_terms)}"

        elif speech_score >= 2 and visual_score == 0:
            # Strong speech signal
            suggested_mode = "skip"
            suggested_weight_adjustment = -0.20  # Reduce visual weight
            confidence = 0.9
            explanation = f"Strong speech intent: {', '.join(speech_terms)}"

        elif speech_score >= 1 and visual_score == 0:
            # Moderate speech signal
            suggested_mode = "skip"
            suggested_weight_adjustment = -0.10  # Reduce visual weight
            confidence = 0.7
            explanation = f"Moderate speech intent: {', '.join(speech_terms)}"

        elif visual_score > 0 and speech_score > 0:
            # Mixed signals - use visual score to decide
            if visual_score > speech_score:
                suggested_mode = "rerank"
                suggested_weight_adjustment = 0.0
                confidence = 0.4
                explanation = f"Mixed intent (visual dominant): visual={visual_terms}, speech={speech_terms}"
            else:
                suggested_mode = "rerank"
                suggested_weight_adjustment = -0.05
                confidence = 0.4
                explanation = f"Mixed intent (speech dominant): visual={visual_terms}, speech={speech_terms}"
        else:
            # No clear signals - default to rerank with low weight
            suggested_mode = "rerank"
            suggested_weight_adjustment = 0.0
            confidence = 0.3
            explanation = "No clear visual or speech signals"

        result = VisualIntentResult(
            has_visual_intent=has_visual_intent,
            has_speech_intent=has_speech_intent,
            confidence=confidence,
            matched_visual_terms=visual_terms,
            matched_speech_terms=speech_terms,
            suggested_mode=suggested_mode,
            suggested_weight_adjustment=suggested_weight_adjustment,
            explanation=explanation,
        )

        logger.debug(
            f"Visual intent analysis: query='{query[:50]}...', "
            f"mode={result.suggested_mode}, confidence={result.confidence:.2f}, "
            f"visual_terms={visual_terms}, speech_terms={speech_terms}"
        )

        return result

    def _normalize_query(self, query_lower: str) -> str:
        """Normalize query for matching (remove punctuation, extra spaces)."""
        # Remove punctuation except hyphens
        normalized = re.sub(r'[^\w\s-]', ' ', query_lower)
        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _match_visual_terms(self, query_lower: str, query_normalized: str) -> list[str]:
        """Find visual terms in query."""
        matched = []

        # Check phrases first (more specific)
        for phrase in VISUAL_PHRASES:
            if phrase in query_lower:
                matched.append(f"phrase:{phrase}")

        # Check individual words
        words = set(query_normalized.split())

        for obj in VISUAL_OBJECTS:
            if obj in words or obj in query_normalized:
                matched.append(f"object:{obj}")

        for action in VISUAL_ACTIONS:
            if action in words or action in query_normalized:
                matched.append(f"action:{action}")

        for attr in VISUAL_ATTRIBUTES:
            if attr in words or attr in query_normalized:
                matched.append(f"attr:{attr}")

        return matched

    def _match_speech_terms(self, query_lower: str, query_normalized: str) -> list[str]:
        """Find speech/dialogue terms in query."""
        matched = []

        # Check phrases first
        for phrase in SPEECH_PHRASES:
            if phrase in query_lower:
                matched.append(f"phrase:{phrase}")

        # Check keywords
        words = set(query_normalized.split())
        for keyword in SPEECH_KEYWORDS:
            if keyword in words or keyword in query_normalized:
                matched.append(f"keyword:{keyword}")

        return matched


# Global router instance
_router: Optional[VisualIntentRouter] = None


def get_visual_intent_router() -> VisualIntentRouter:
    """Get or create the global visual intent router instance."""
    global _router
    if _router is None:
        _router = VisualIntentRouter()
    return _router
