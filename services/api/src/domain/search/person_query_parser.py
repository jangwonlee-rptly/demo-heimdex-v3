"""Person query parser for deterministic person name extraction."""
import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class PersonQueryParser:
    """Parses search queries to extract person names deterministically."""

    def __init__(self, db, owner_id: UUID):
        """Initialize parser with person lookup.

        Args:
            db: Database adapter
            owner_id: UUID of the current user
        """
        self.db = db
        self.owner_id = owner_id
        self._load_persons()

    def _load_persons(self) -> None:
        """Load persons and build lookup dictionary."""
        persons = self.db.list_persons(owner_id=self.owner_id)

        # Build lookup: lowercase display_name -> (person_id, embedding)
        # Sort by length DESC to match longest names first (avoid prefix collisions)
        self.person_lookup = {}

        for person in persons:
            if person.display_name:
                key = person.display_name.lower().strip()
                if key:
                    self.person_lookup[key] = {
                        "person_id": person.id,
                        "embedding": person.query_embedding,
                    }

        logger.debug(f"Loaded {len(self.person_lookup)} persons for query parsing")

    def parse(self, query: str) -> tuple[Optional[UUID], Optional[list[float]], str]:
        """Parse query to extract person.

        Supports two patterns:
        1. "person:<name>, <rest>" - explicit person prefix
        2. "<name> <rest>" - name at start (case-insensitive)

        Args:
            query: User search query

        Returns:
            tuple of (person_id, person_embedding, remaining_query):
            - person_id: UUID if person found, else None
            - person_embedding: embedding list if exists, else None
            - remaining_query: query with person name removed
        """
        if not query:
            return None, None, query

        query_lower = query.lower().strip()

        # Pattern 1: "person:<name>, <rest>"
        if query_lower.startswith("person:"):
            # Extract name after "person:" until comma or end
            rest = query[7:].strip()  # Skip "person:"

            # Find comma separator
            comma_idx = rest.find(",")
            if comma_idx > 0:
                name_part = rest[:comma_idx].strip()
                remaining = rest[comma_idx + 1:].strip()
            else:
                name_part = rest.strip()
                remaining = ""

            # Look up person by name
            name_lower = name_part.lower()
            if name_lower in self.person_lookup:
                person_data = self.person_lookup[name_lower]
                logger.info(f"Parsed person via prefix: '{name_part}' -> {person_data['person_id']}")
                return (
                    person_data["person_id"],
                    person_data["embedding"],
                    remaining,
                )
            else:
                logger.info(f"Person '{name_part}' not found (prefix pattern)")
                return None, None, query

        # Pattern 2: "<name> <rest>" - name at start
        # Sort names by length DESC to match longest first
        sorted_names = sorted(self.person_lookup.keys(), key=len, reverse=True)

        for name in sorted_names:
            if query_lower.startswith(name):
                # Check that match is word-boundary (not prefix of another word)
                # Either end of string or followed by space/punctuation
                match_end = len(name)
                if match_end < len(query_lower):
                    next_char = query_lower[match_end]
                    if next_char not in (" ", ",", ".", "!", "?"):
                        # Not a word boundary, skip
                        continue

                # Found match
                person_data = self.person_lookup[name]
                # Use query_lower (stripped) for extraction to align indices
                remaining = query_lower[match_end:].strip()

                # Remove leading comma/punctuation from remaining
                if remaining and remaining[0] in (",", ".", "!"):
                    remaining = remaining[1:].strip()

                logger.info(f"Parsed person at start: '{name}' -> {person_data['person_id']}")
                return (
                    person_data["person_id"],
                    person_data["embedding"],
                    remaining,
                )

        # No person detected
        return None, None, query
