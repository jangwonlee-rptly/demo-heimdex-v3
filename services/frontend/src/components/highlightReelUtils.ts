/**
 * Utility functions for Highlight Reel Builder functionality.
 * Pure functions for managing scene selection, reordering, and export.
 */

import type { VideoScene } from '@/types';

/**
 * Minimal scene data needed for the selection tray and export.
 */
export interface SelectedScene {
  scene_id: string;
  video_id: string;
  video_filename: string;
  start_s: number;
  end_s: number;
  thumbnail_url: string | null;
  index: number;
}

/**
 * Export payload structure for the highlight reel.
 */
export interface HighlightExportPayload {
  scenes: Array<{
    scene_id: string;
    video_id: string;
    start_s: number;
    end_s: number;
  }>;
  total_duration_s: number;
  scene_count: number;
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
 * Converts a VideoScene to a SelectedScene with minimal fields.
 *
 * @param {VideoScene} scene - Full VideoScene from search results.
 * @returns {SelectedScene} SelectedScene with fields needed for tray + export.
 */
export function toSelectedScene(scene: VideoScene): SelectedScene {
  return {
    scene_id: scene.id,
    video_id: scene.video_id,
    video_filename: scene.video_filename || `Untitled (${shortId(scene.video_id)})`,
    start_s: scene.start_s,
    end_s: scene.end_s,
    thumbnail_url: scene.thumbnail_url || null,
    index: scene.index,
  };
}

/**
 * Adds a scene to the selection if not already present.
 * Appends to end; maintains insertion order.
 *
 * @param {SelectedScene[]} selected - Current selection array.
 * @param {SelectedScene} scene - Scene to add.
 * @returns {SelectedScene[]} New array with scene appended (or unchanged if duplicate).
 */
export function addSelected(
  selected: SelectedScene[],
  scene: SelectedScene
): SelectedScene[] {
  const exists = selected.some((s) => s.scene_id === scene.scene_id);
  if (exists) {
    return selected;
  }
  return [...selected, scene];
}

/**
 * Removes a scene from the selection by scene_id.
 *
 * @param {SelectedScene[]} selected - Current selection array.
 * @param {string} sceneId - ID of scene to remove.
 * @returns {SelectedScene[]} New array without the specified scene.
 */
export function removeSelected(
  selected: SelectedScene[],
  sceneId: string
): SelectedScene[] {
  return selected.filter((s) => s.scene_id !== sceneId);
}

/**
 * Reorders a scene from one index to another.
 * Uses stable array splice approach.
 *
 * @param {SelectedScene[]} selected - Current selection array.
 * @param {number} fromIndex - Source index.
 * @param {number} toIndex - Destination index.
 * @returns {SelectedScene[]} New array with reordered items.
 */
export function reorderSelected(
  selected: SelectedScene[],
  fromIndex: number,
  toIndex: number
): SelectedScene[] {
  if (
    fromIndex < 0 ||
    fromIndex >= selected.length ||
    toIndex < 0 ||
    toIndex >= selected.length ||
    fromIndex === toIndex
  ) {
    return selected;
  }

  const result = [...selected];
  const [removed] = result.splice(fromIndex, 1);
  result.splice(toIndex, 0, removed);
  return result;
}

/**
 * Calculates total duration of selected scenes.
 *
 * @param {SelectedScene[]} selected - Array of selected scenes.
 * @returns {number} Total duration in seconds.
 */
export function totalDuration(selected: SelectedScene[]): number {
  return selected.reduce((sum, s) => sum + (s.end_s - s.start_s), 0);
}

/**
 * Checks if a scene is currently selected.
 *
 * @param {SelectedScene[]} selected - Current selection array.
 * @param {string} sceneId - Scene ID to check.
 * @returns {boolean} true if scene is selected.
 */
export function isSceneSelected(
  selected: SelectedScene[],
  sceneId: string
): boolean {
  return selected.some((s) => s.scene_id === sceneId);
}

/**
 * Builds the export payload for the highlight reel.
 *
 * @param {SelectedScene[]} selected - Ordered array of selected scenes.
 * @returns {HighlightExportPayload} Export payload object ready for API.
 */
export function buildExportPayload(
  selected: SelectedScene[]
): HighlightExportPayload {
  return {
    scenes: selected.map((s) => ({
      scene_id: s.scene_id,
      video_id: s.video_id,
      start_s: s.start_s,
      end_s: s.end_s,
    })),
    total_duration_s: totalDuration(selected),
    scene_count: selected.length,
  };
}

/**
 * Formats duration in seconds to mm:ss display format.
 *
 * @param {number} seconds - Duration in seconds.
 * @returns {string} Formatted string like "2:30".
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
