/**
 * API Configuration
 *
 * Centralizes API versioning and endpoint construction.
 * This makes it easy to update API versions in the future.
 */

/**
 * Current API version prefix.
 * Update this when migrating to a new API version.
 */
export const API_VERSION = 'v1';

/**
 * Construct a versioned API endpoint path.
 *
 * @param {string} path - The endpoint path (e.g., "/videos", "/search")
 * @returns {string} The versioned endpoint path (e.g., "/v1/videos")
 *
 * @example
 * apiEndpoint('/videos') // Returns: "/v1/videos"
 * apiEndpoint('/search') // Returns: "/v1/search"
 */
export function apiEndpoint(path: string): string {
  // Health check endpoints don't use versioning
  if (path.startsWith('/health')) {
    return path;
  }

  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  // Return versioned path
  return `/${API_VERSION}${normalizedPath}`;
}
