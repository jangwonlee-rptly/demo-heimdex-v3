import { createClient } from '@supabase/supabase-js';
import { apiEndpoint } from './api-config';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Get the current access token for API requests.
 *
 * @returns {Promise<string | null>} The access token if a session exists, or null.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || null;
}

/**
 * Make an authenticated API request with automatic versioning.
 *
 * @template T
 * @param {string} endpoint - The API endpoint to call (e.g., "/videos").
 *                           Will be automatically versioned (e.g., "/v1/videos").
 * @param {RequestInit} [options={}] - Fetch options including method, body, etc.
 * @returns {Promise<T>} The response data parsed as JSON.
 * @throws {Error} If the API request fails (non-2xx status).
 *
 * @example
 * // Automatically becomes /v1/videos
 * const videos = await apiRequest<VideoList>('/videos');
 *
 * // POST to /v1/search
 * const results = await apiRequest<SearchResults>('/search', {
 *   method: 'POST',
 *   body: JSON.stringify({ query: 'test' })
 * });
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAccessToken();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Apply API versioning
  const versionedEndpoint = apiEndpoint(endpoint);

  const response = await fetch(`${apiUrl}${versionedEndpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API request failed: ${response.statusText}`);
  }

  return response.json();
}
