/**
 * Utility functions for file toggle functionality in search results.
 */

import type { VideoScene } from '@/types';

export interface GroupedFile {
  videoId: string;
  filename: string;
  sceneCount: number;
}

/**
 * Shortens a UUID for display (first 8 characters).
 *
 * @param {string} uuid - The full UUID string.
 * @returns {string} The first 8 characters of the UUID.
 */
function shortId(uuid: string): string {
  return uuid.slice(0, 8);
}

/**
 * Groups scenes by video_id and returns aggregated file information.
 *
 * Used to populate the FileToggleBar with a list of files found in search results.
 *
 * @param {VideoScene[]} scenes - Array of video scenes from search results.
 * @returns {GroupedFile[]} Array of grouped files sorted by scene count (desc), then filename (asc).
 */
export function groupScenesByVideo(scenes: VideoScene[]): GroupedFile[] {
  const grouped = new Map<string, { filename: string | null; count: number }>();

  for (const scene of scenes) {
    const existing = grouped.get(scene.video_id);
    if (existing) {
      existing.count++;
    } else {
      grouped.set(scene.video_id, {
        filename: scene.video_filename || null,
        count: 1,
      });
    }
  }

  const files = Array.from(grouped.entries()).map(([videoId, data]) => ({
    videoId,
    filename: data.filename || `Untitled (${shortId(videoId)})`,
    sceneCount: data.count,
  }));

  // Sort by scene count descending, then filename ascending
  files.sort((a, b) => {
    if (a.sceneCount !== b.sceneCount) {
      return b.sceneCount - a.sceneCount;
    }
    return a.filename.localeCompare(b.filename);
  });

  return files;
}

/**
 * Filters scenes based on file toggle states.
 * If a video_id is not in toggles or is true, the scene is visible.
 * If a video_id is explicitly false, the scene is hidden.
 *
 * @param {VideoScene[]} scenes - Array of video scenes to filter.
 * @param {Record<string, boolean>} toggles - Record of video_id to enabled/disabled state.
 * @returns {VideoScene[]} Filtered array of visible scenes.
 */
export function filterScenesByToggles(
  scenes: VideoScene[],
  toggles: Record<string, boolean>
): VideoScene[] {
  return scenes.filter((scene) => {
    const toggleState = toggles[scene.video_id];
    // If key missing or explicitly true, show the scene
    // If explicitly false, hide the scene
    return toggleState !== false;
  });
}

/**
 * Creates initial toggle state with all video IDs enabled.
 *
 * @param {string[]} videoIds - Array of unique video IDs.
 * @returns {Record<string, boolean>} Record with all video IDs set to true.
 */
export function createInitialToggles(videoIds: string[]): Record<string, boolean> {
  return Object.fromEntries(videoIds.map((id) => [id, true]));
}

/**
 * Extracts unique video IDs from scenes.
 *
 * @param {VideoScene[]} scenes - Array of video scenes.
 * @returns {string[]} Array of unique video IDs.
 */
export function extractUniqueVideoIds(scenes: VideoScene[]): string[] {
  return Array.from(new Set(scenes.map((scene) => scene.video_id)));
}
