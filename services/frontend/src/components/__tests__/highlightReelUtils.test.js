/**
 * Tests for Highlight Reel utility functions.
 *
 * Run with: node services/frontend/src/components/__tests__/highlightReelUtils.test.js
 *
 * Note: This is a minimal Node-runnable test since no test framework is installed.
 */

// Mock VideoScene data for testing
function createMockVideoScene(overrides = {}) {
  return {
    id: overrides.id || `scene-${Math.random().toString(36).slice(2)}`,
    video_id: overrides.video_id || 'video-123',
    video_filename: overrides.video_filename || 'Test Video.mp4',
    index: overrides.index ?? 0,
    start_s: overrides.start_s ?? 0,
    end_s: overrides.end_s ?? 10,
    thumbnail_url: overrides.thumbnail_url || 'https://example.com/thumb.jpg',
    created_at: '2024-01-01T00:00:00Z',
  };
}

// Inline implementations (since we can't import TS modules in plain Node)
function shortId(uuid) {
  return uuid.slice(0, 8);
}

function toSelectedScene(scene) {
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

function addSelected(selected, scene) {
  const exists = selected.some((s) => s.scene_id === scene.scene_id);
  if (exists) {
    return selected;
  }
  return [...selected, scene];
}

function removeSelected(selected, sceneId) {
  return selected.filter((s) => s.scene_id !== sceneId);
}

function reorderSelected(selected, fromIndex, toIndex) {
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

function totalDuration(selected) {
  return selected.reduce((sum, s) => sum + (s.end_s - s.start_s), 0);
}

function isSceneSelected(selected, sceneId) {
  return selected.some((s) => s.scene_id === sceneId);
}

function buildExportPayload(selected) {
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

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Test utilities
let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAIL: ${message}`);
    testsFailed++;
    return false;
  }
  console.log(`✅ PASS: ${message}`);
  testsPassed++;
  return true;
}

function assertEquals(actual, expected, message) {
  const passed = JSON.stringify(actual) === JSON.stringify(expected);
  if (!passed) {
    console.error(`❌ FAIL: ${message}`);
    console.error(`  Expected: ${JSON.stringify(expected)}`);
    console.error(`  Actual:   ${JSON.stringify(actual)}`);
    testsFailed++;
    return false;
  }
  console.log(`✅ PASS: ${message}`);
  testsPassed++;
  return true;
}

// Tests
console.log('\n🧪 Running Highlight Reel Utils Tests\n');

// Test 1: toSelectedScene - basic conversion
{
  const scene = createMockVideoScene({
    id: 'scene-abc',
    video_id: 'video-xyz',
    video_filename: 'Movie.mp4',
    index: 3,
    start_s: 10,
    end_s: 25,
    thumbnail_url: 'https://example.com/t.jpg',
  });
  const result = toSelectedScene(scene);

  assert(result.scene_id === 'scene-abc', 'toSelectedScene: maps id to scene_id');
  assert(result.video_id === 'video-xyz', 'toSelectedScene: preserves video_id');
  assert(result.video_filename === 'Movie.mp4', 'toSelectedScene: preserves filename');
  assert(result.index === 3, 'toSelectedScene: preserves index');
}

// Test 2: toSelectedScene - fallback label for missing filename
{
  const videoId = '12345678-1234-1234-1234-123456789abc';
  const scene = {
    id: 'scene-123',
    video_id: videoId,
    video_filename: null,  // explicitly null
    index: 0,
    start_s: 0,
    end_s: 10,
    thumbnail_url: null,
    created_at: '2024-01-01T00:00:00Z',
  };
  const result = toSelectedScene(scene);

  assert(result.video_filename.startsWith('Untitled ('), 'toSelectedScene: fallback starts with Untitled');
  assert(result.video_filename.includes('12345678'), 'toSelectedScene: fallback includes short ID');
}

// Test 3: addSelected - appends new scene
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));

  let selected = [];
  selected = addSelected(selected, scene1);
  selected = addSelected(selected, scene2);

  assert(selected.length === 2, 'addSelected: appends scenes');
  assert(selected[0].scene_id === 'scene-1', 'addSelected: first scene preserved');
  assert(selected[1].scene_id === 'scene-2', 'addSelected: second scene appended');
}

// Test 4: addSelected - prevents duplicates
{
  const scene = toSelectedScene(createMockVideoScene({ id: 'scene-dup' }));

  let selected = [];
  selected = addSelected(selected, scene);
  selected = addSelected(selected, scene);
  selected = addSelected(selected, scene);

  assert(selected.length === 1, 'addSelected: no duplicates (added 3x, length is 1)');
}

// Test 5: addSelected - preserves order on duplicate add
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));
  const scene3 = toSelectedScene(createMockVideoScene({ id: 'scene-3' }));

  let selected = [scene1, scene2, scene3];
  const beforeAdd = [...selected];
  selected = addSelected(selected, scene2); // duplicate

  assertEquals(selected, beforeAdd, 'addSelected: order unchanged on duplicate');
}

// Test 6: removeSelected - removes existing scene
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));

  let selected = [scene1, scene2];
  selected = removeSelected(selected, 'scene-1');

  assert(selected.length === 1, 'removeSelected: removes scene');
  assert(selected[0].scene_id === 'scene-2', 'removeSelected: correct scene remains');
}

// Test 7: removeSelected - handles non-existent scene
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));

  let selected = [scene1];
  selected = removeSelected(selected, 'non-existent');

  assert(selected.length === 1, 'removeSelected: no change for non-existent scene');
}

// Test 8: reorderSelected - move forward
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));
  const scene3 = toSelectedScene(createMockVideoScene({ id: 'scene-3' }));

  let selected = [scene1, scene2, scene3];
  selected = reorderSelected(selected, 0, 2); // move first to last

  assert(selected[0].scene_id === 'scene-2', 'reorderSelected: scene-2 now first');
  assert(selected[1].scene_id === 'scene-3', 'reorderSelected: scene-3 now second');
  assert(selected[2].scene_id === 'scene-1', 'reorderSelected: scene-1 now last');
}

// Test 9: reorderSelected - move backward
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));
  const scene3 = toSelectedScene(createMockVideoScene({ id: 'scene-3' }));

  let selected = [scene1, scene2, scene3];
  selected = reorderSelected(selected, 2, 0); // move last to first

  assert(selected[0].scene_id === 'scene-3', 'reorderSelected backward: scene-3 now first');
  assert(selected[1].scene_id === 'scene-1', 'reorderSelected backward: scene-1 now second');
  assert(selected[2].scene_id === 'scene-2', 'reorderSelected backward: scene-2 now last');
}

// Test 10: reorderSelected - same index (no-op)
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));

  let selected = [scene1, scene2];
  const beforeReorder = [...selected];
  selected = reorderSelected(selected, 1, 1);

  assertEquals(selected, beforeReorder, 'reorderSelected: no change when from === to');
}

// Test 11: reorderSelected - out of bounds
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));

  let selected = [scene1];
  const beforeReorder = [...selected];
  selected = reorderSelected(selected, -1, 0); // invalid from
  selected = reorderSelected(selected, 0, 5);  // invalid to

  assertEquals(selected, beforeReorder, 'reorderSelected: no change for invalid indices');
}

// Test 12: totalDuration - single scene
{
  const scene = toSelectedScene(createMockVideoScene({ start_s: 5, end_s: 15 }));
  const duration = totalDuration([scene]);

  assert(duration === 10, 'totalDuration: single scene (15-5=10)');
}

// Test 13: totalDuration - multiple scenes
{
  const scene1 = toSelectedScene(createMockVideoScene({ start_s: 0, end_s: 10 }));
  const scene2 = toSelectedScene(createMockVideoScene({ start_s: 5, end_s: 20 }));
  const scene3 = toSelectedScene(createMockVideoScene({ start_s: 0, end_s: 5 }));

  const duration = totalDuration([scene1, scene2, scene3]);

  assert(duration === 30, 'totalDuration: multiple scenes (10 + 15 + 5 = 30)');
}

// Test 14: totalDuration - empty array
{
  const duration = totalDuration([]);

  assert(duration === 0, 'totalDuration: empty array returns 0');
}

// Test 15: isSceneSelected - found
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));
  const scene2 = toSelectedScene(createMockVideoScene({ id: 'scene-2' }));

  assert(isSceneSelected([scene1, scene2], 'scene-1'), 'isSceneSelected: finds scene-1');
  assert(isSceneSelected([scene1, scene2], 'scene-2'), 'isSceneSelected: finds scene-2');
}

// Test 16: isSceneSelected - not found
{
  const scene1 = toSelectedScene(createMockVideoScene({ id: 'scene-1' }));

  assert(!isSceneSelected([scene1], 'scene-999'), 'isSceneSelected: returns false for missing');
  assert(!isSceneSelected([], 'scene-1'), 'isSceneSelected: returns false for empty array');
}

// Test 17: buildExportPayload - structure
{
  const scene1 = toSelectedScene(createMockVideoScene({
    id: 'scene-1',
    video_id: 'video-1',
    start_s: 0,
    end_s: 10
  }));
  const scene2 = toSelectedScene(createMockVideoScene({
    id: 'scene-2',
    video_id: 'video-2',
    start_s: 5,
    end_s: 15
  }));

  const payload = buildExportPayload([scene1, scene2]);

  assert(payload.scene_count === 2, 'buildExportPayload: correct scene count');
  assert(payload.total_duration_s === 20, 'buildExportPayload: correct total duration');
  assert(payload.scenes.length === 2, 'buildExportPayload: scenes array present');
  assert(payload.scenes[0].scene_id === 'scene-1', 'buildExportPayload: preserves order');
}

// Test 18: buildExportPayload - scene structure
{
  const scene = toSelectedScene(createMockVideoScene({
    id: 'scene-abc',
    video_id: 'video-xyz',
    start_s: 100,
    end_s: 200
  }));

  const payload = buildExportPayload([scene]);
  const payloadScene = payload.scenes[0];

  assert(payloadScene.scene_id === 'scene-abc', 'buildExportPayload scene: has scene_id');
  assert(payloadScene.video_id === 'video-xyz', 'buildExportPayload scene: has video_id');
  assert(payloadScene.start_s === 100, 'buildExportPayload scene: has start_s');
  assert(payloadScene.end_s === 200, 'buildExportPayload scene: has end_s');
  assert(!('video_filename' in payloadScene), 'buildExportPayload scene: no extra fields');
}

// Test 19: formatDuration - various values
{
  assert(formatDuration(0) === '0:00', 'formatDuration: 0 seconds');
  assert(formatDuration(30) === '0:30', 'formatDuration: 30 seconds');
  assert(formatDuration(60) === '1:00', 'formatDuration: 60 seconds');
  assert(formatDuration(90) === '1:30', 'formatDuration: 90 seconds');
  assert(formatDuration(125) === '2:05', 'formatDuration: 125 seconds');
  assert(formatDuration(3661) === '61:01', 'formatDuration: 1 hour+');
}

// Test 20: Integration - complete workflow
{
  // Simulate user selecting, reordering, and exporting
  const videoScene1 = createMockVideoScene({ id: 's1', start_s: 0, end_s: 10 });
  const videoScene2 = createMockVideoScene({ id: 's2', start_s: 20, end_s: 35 });
  const videoScene3 = createMockVideoScene({ id: 's3', start_s: 40, end_s: 50 });

  // Convert to selected scenes
  const sel1 = toSelectedScene(videoScene1);
  const sel2 = toSelectedScene(videoScene2);
  const sel3 = toSelectedScene(videoScene3);

  // Add in order
  let selected = [];
  selected = addSelected(selected, sel1);
  selected = addSelected(selected, sel2);
  selected = addSelected(selected, sel3);
  assert(selected.length === 3, 'Integration: added 3 scenes');

  // Check duration
  assert(totalDuration(selected) === 35, 'Integration: total duration is 10+15+10=35');

  // Reorder: move sel3 to first position
  selected = reorderSelected(selected, 2, 0);
  assert(selected[0].scene_id === 's3', 'Integration: s3 is now first');

  // Remove middle scene
  selected = removeSelected(selected, 's1');
  assert(selected.length === 2, 'Integration: 2 scenes after removal');

  // Build export payload
  const payload = buildExportPayload(selected);
  assert(payload.scene_count === 2, 'Integration: payload has 2 scenes');
  assert(payload.scenes[0].scene_id === 's3', 'Integration: export order correct (s3 first)');
  assert(payload.scenes[1].scene_id === 's2', 'Integration: export order correct (s2 second)');
}

// Summary
console.log('\n' + '='.repeat(50));
console.log(`✅ Passed: ${testsPassed}`);
console.log(`❌ Failed: ${testsFailed}`);
console.log('='.repeat(50) + '\n');

if (testsFailed > 0) {
  process.exit(1);
}
