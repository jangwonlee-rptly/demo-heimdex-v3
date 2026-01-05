"""Unit tests for person query parser."""
import pytest
from uuid import UUID

from src.domain.search.person_query_parser import PersonQueryParser
from src.domain.models import Person


class StubDatabase:
    """Minimal stub database implementing only list_persons."""

    def __init__(self, persons: list[Person]):
        """Initialize with a list of persons.

        Args:
            persons: List of Person objects to return from list_persons
        """
        self.persons = persons

    def list_persons(self, owner_id: UUID) -> list[Person]:
        """Return pre-configured persons.

        Args:
            owner_id: Owner UUID (not validated in stub)

        Returns:
            List of Person objects
        """
        return self.persons


class TestPersonQueryParserPrefixPattern:
    """Tests for 'person:<name>, <rest>' prefix pattern."""

    def test_prefix_with_embedding(self):
        """Parse 'person:j lee, doing pushups' with embedding."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")
        embedding = [0.1] * 512

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=embedding,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("person:j lee, doing pushups")

        assert result_id == person_id
        assert result_emb == embedding
        assert remaining == "doing pushups"

    def test_prefix_without_embedding(self):
        """Parse 'person:j lee, doing pushups' without embedding (None)."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=None,  # No embedding yet
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("person:j lee, doing pushups")

        assert result_id == person_id
        assert result_emb is None
        assert remaining == "doing pushups"

    def test_prefix_case_insensitive(self):
        """Parse 'PERSON:J LEE, doing pushups' (uppercase) matches person."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")
        embedding = [0.1] * 512

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="j lee",  # lowercase in DB
                query_embedding=embedding,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("PERSON:J LEE, doing pushups")

        assert result_id == person_id
        assert result_emb == embedding
        assert remaining == "doing pushups"

    def test_prefix_no_comma_separator(self):
        """Parse 'person:j lee' without comma returns empty remaining."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("person:j lee")

        assert result_id == person_id
        assert remaining == ""

    def test_prefix_person_not_found(self):
        """Parse 'person:unknown, query' returns None when person not found."""
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=UUID("12345678-1234-1234-1234-123456789abc"),
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("person:unknown, doing pushups")

        assert result_id is None
        assert result_emb is None
        assert remaining == "person:unknown, doing pushups"  # Original query unchanged


class TestPersonQueryParserNameAtStart:
    """Tests for '<name> <rest>' name-at-start pattern."""

    def test_name_at_start_with_space(self):
        """Parse 'j lee doing pushups' (name at start, space separator)."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")
        embedding = [0.1] * 512

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=embedding,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee doing pushups")

        assert result_id == person_id
        assert result_emb == embedding
        assert remaining == "doing pushups"

    def test_name_at_start_with_comma(self):
        """Parse 'j lee, doing pushups' strips comma from remaining."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee, doing pushups")

        assert result_id == person_id
        assert remaining == "doing pushups"  # Comma stripped

    def test_name_at_start_with_colon(self):
        """Parse 'j lee: doing pushups' (colon is NOT a word boundary, no match)."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee: doing pushups")

        # Colon is not a valid word boundary character, so no match
        assert result_id is None
        assert result_emb is None
        assert remaining == "j lee: doing pushups"

    def test_name_at_start_case_insensitive(self):
        """Parse 'J LEE doing pushups' (uppercase) matches lowercase person."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="j lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("J LEE doing pushups")

        assert result_id == person_id
        assert remaining == "doing pushups"


class TestPersonQueryParserLongestMatchFirst:
    """Tests for longest-name-first matching logic."""

    def test_longest_name_wins(self):
        """When 'J' and 'J Lee' both exist, 'j lee query' resolves to 'J Lee'."""
        j_id = UUID("11111111-1111-1111-1111-111111111111")
        j_lee_id = UUID("22222222-2222-2222-2222-222222222222")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=j_id,
                owner_id=owner_id,
                display_name="J",
                query_embedding=[0.1] * 512,
                status="active",
            ),
            Person(
                id=j_lee_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.2] * 512,
                status="active",
            ),
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee doing pushups")

        # Should match "J Lee", not "J"
        assert result_id == j_lee_id
        assert result_emb == [0.2] * 512
        assert remaining == "doing pushups"

    def test_longest_match_prevents_prefix_collision(self):
        """Ensure 'John' and 'John Smith' don't collide on prefix."""
        john_id = UUID("11111111-1111-1111-1111-111111111111")
        john_smith_id = UUID("22222222-2222-2222-2222-222222222222")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=john_id,
                owner_id=owner_id,
                display_name="John",
                query_embedding=[0.1] * 512,
                status="active",
            ),
            Person(
                id=john_smith_id,
                owner_id=owner_id,
                display_name="John Smith",
                query_embedding=[0.2] * 512,
                status="active",
            ),
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        # Query: "john smith running"
        result_id, _, remaining = parser.parse("john smith running")
        assert result_id == john_smith_id
        assert remaining == "running"

        # Query: "john running" (shorter name)
        result_id, _, remaining = parser.parse("john running")
        assert result_id == john_id
        assert remaining == "running"


class TestPersonQueryParserWordBoundary:
    """Tests for word boundary detection."""

    def test_word_boundary_space(self):
        """Name followed by space is valid word boundary."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, _, remaining = parser.parse("lee running")

        assert result_id == person_id
        assert remaining == "running"

    def test_word_boundary_comma(self):
        """Name followed by comma is valid word boundary."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, _, remaining = parser.parse("lee, running")

        assert result_id == person_id
        assert remaining == "running"

    def test_not_word_boundary_letter(self):
        """Name followed by letter is NOT a word boundary (should not match)."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        # "leeway" should NOT match "Lee"
        result_id, result_emb, remaining = parser.parse("leeway running")

        assert result_id is None
        assert result_emb is None
        assert remaining == "leeway running"


class TestPersonQueryParserEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self):
        """Empty query returns None, None, empty string."""
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")
        persons = []

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("")

        assert result_id is None
        assert result_emb is None
        assert remaining == ""

    def test_no_persons_in_db(self):
        """Parser with empty person list returns None."""
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")
        persons = []

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee doing pushups")

        assert result_id is None
        assert result_emb is None
        assert remaining == "j lee doing pushups"

    def test_person_with_no_display_name(self):
        """Person with display_name=None is skipped in lookup."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name=None,  # No display name
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        # Parser should have 0 persons in lookup
        assert len(parser.person_lookup) == 0

        result_id, result_emb, remaining = parser.parse("anything")
        assert result_id is None

    def test_person_with_empty_display_name(self):
        """Person with display_name='' is skipped in lookup."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="   ",  # Whitespace only
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        # Parser should have 0 persons in lookup (whitespace stripped to empty)
        assert len(parser.person_lookup) == 0

    def test_no_match_returns_original_query(self):
        """When no person matches, original query is returned unchanged."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        original_query = "someone else doing pushups"
        result_id, result_emb, remaining = parser.parse(original_query)

        assert result_id is None
        assert result_emb is None
        assert remaining == original_query

    def test_name_at_end_of_query(self):
        """Name at start (end of query) with no remaining text."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("j lee")

        assert result_id == person_id
        assert remaining == ""

    def test_query_with_leading_trailing_whitespace(self):
        """Query with extra whitespace is handled correctly."""
        person_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = UUID("87654321-4321-4321-4321-cba987654321")

        persons = [
            Person(
                id=person_id,
                owner_id=owner_id,
                display_name="J Lee",
                query_embedding=[0.1] * 512,
                status="active",
            )
        ]

        db = StubDatabase(persons)
        parser = PersonQueryParser(db, owner_id)

        result_id, result_emb, remaining = parser.parse("  j lee doing pushups  ")

        assert result_id == person_id
        assert remaining == "doing pushups"
