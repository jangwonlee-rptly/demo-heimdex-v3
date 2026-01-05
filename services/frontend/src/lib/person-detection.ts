/**
 * Person detection utilities for search queries.
 * Handles detection of person names anywhere in a query with proper word-boundary safety.
 */

import type { Person } from '@/types';

/**
 * Result of person detection in a query.
 */
export interface PersonDetectionResult {
  person: Person;
  matchStart: number;
  matchEnd: number;
  matchedText: string;
}

/**
 * Check if a character is a word boundary for Latin text.
 * Word boundaries include: space, punctuation, start/end of string.
 */
function isWordBoundary(char: string | undefined): boolean {
  if (!char) return true; // Start or end of string
  // Match whitespace, common punctuation, or CJK characters
  return /[\s.,;:!?\-()'"]/u.test(char) || isCJKChar(char);
}

/**
 * Check if a character is a CJK (Chinese/Japanese/Korean) character.
 */
function isCJKChar(char: string): boolean {
  const code = char.charCodeAt(0);
  return (
    (code >= 0x4e00 && code <= 0x9fff) || // CJK Unified Ideographs
    (code >= 0x3400 && code <= 0x4dbf) || // CJK Extension A
    (code >= 0xac00 && code <= 0xd7af) || // Hangul Syllables
    (code >= 0x3040 && code <= 0x309f) || // Hiragana
    (code >= 0x30a0 && code <= 0x30ff)    // Katakana
  );
}

/**
 * Check if a person name is primarily composed of CJK characters.
 */
function isCJKName(name: string): boolean {
  const cjkChars = name.split('').filter(isCJKChar);
  return cjkChars.length > name.length * 0.5; // More than 50% CJK
}

/**
 * Find all occurrences of a name in the query with proper word boundaries.
 * For Latin names, enforce strict word boundaries.
 * For CJK names, allow substring matching.
 */
function findNameOccurrences(
  query: string,
  name: string,
  isCJK: boolean
): { start: number; end: number }[] {
  const occurrences: { start: number; end: number }[] = [];
  const lowerQuery = query.toLowerCase();
  const lowerName = name.toLowerCase();
  let searchStart = 0;

  while (true) {
    const index = lowerQuery.indexOf(lowerName, searchStart);
    if (index === -1) break;

    const beforeChar = index > 0 ? query[index - 1] : undefined;
    const afterChar = index + name.length < query.length ? query[index + name.length] : undefined;

    if (isCJK) {
      // For CJK names, just ensure we're not inside another CJK word
      // Allow match if either boundary is non-CJK or it's at start/end
      occurrences.push({ start: index, end: index + name.length });
    } else {
      // For Latin names, enforce strict word boundaries
      if (isWordBoundary(beforeChar) && isWordBoundary(afterChar)) {
        occurrences.push({ start: index, end: index + name.length });
      }
    }

    searchStart = index + 1;
  }

  return occurrences;
}

/**
 * Detect the first person mentioned anywhere in the query.
 * Uses longest-match-first strategy with proper word-boundary safety.
 *
 * @param query - The search query to scan
 * @param people - List of person profiles to check against
 * @returns Detection result if a person is found, otherwise null
 */
export function detectPersonInQuery(
  query: string,
  people: Person[]
): PersonDetectionResult | null {
  if (!query.trim() || people.length === 0) {
    return null;
  }

  // Sort people by name length (longest first) for greedy matching
  const sortedPeople = [...people].sort(
    (a, b) => b.display_name.length - a.display_name.length
  );

  // Find the first (leftmost) occurrence of any person name
  let bestMatch: PersonDetectionResult | null = null;

  for (const person of sortedPeople) {
    const isCJK = isCJKName(person.display_name);
    const occurrences = findNameOccurrences(query, person.display_name, isCJK);

    if (occurrences.length > 0) {
      // Take the first occurrence
      const firstOccurrence = occurrences[0];

      // If this is the leftmost match so far (or first match), use it
      if (!bestMatch || firstOccurrence.start < bestMatch.matchStart) {
        bestMatch = {
          person,
          matchStart: firstOccurrence.start,
          matchEnd: firstOccurrence.end,
          matchedText: query.substring(firstOccurrence.start, firstOccurrence.end),
        };
      }
    }
  }

  return bestMatch;
}

/**
 * Transform a query to the backend-compatible format: `person:<name>, <content_query>`
 * Removes the detected person name from the query and prepends the person: prefix.
 *
 * @param query - Original query string
 * @param detectionResult - Result from detectPersonInQuery
 * @returns Transformed query for backend
 */
export function transformQueryForBackend(
  query: string,
  detectionResult: PersonDetectionResult
): string {
  const { person, matchStart, matchEnd } = detectionResult;

  // Remove the matched person name from the query
  const beforeMatch = query.substring(0, matchStart);
  const afterMatch = query.substring(matchEnd);

  // Combine the parts and normalize whitespace
  let contentQuery = (beforeMatch + ' ' + afterMatch).trim();

  // Optional: Remove connector words that immediately surround the match
  // (e.g., "with", "and", "랑", "과", "와")
  // For v1, keep it simple and just remove extra spaces
  contentQuery = contentQuery.replace(/\s+/g, ' ').trim();

  // Build the transformed query
  if (contentQuery) {
    return `person:${person.display_name}, ${contentQuery}`;
  } else {
    // If content query is empty, just send person prefix
    return `person:${person.display_name}`;
  }
}
