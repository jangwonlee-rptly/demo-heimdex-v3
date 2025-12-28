/**
 * Tests for file toggle utility functions.
 *
 * Run with: node services/frontend/src/components/__tests__/fileToggleUtils.test.js
 *
 * Note: This is a minimal Node-runnable test since no test framework is installed.
 * For production, consider installing Jest or Vitest.
 */

// Mock VideoScene data for testing
function createMockScene(videoId, videoFilename = null, sceneId = null) {
  return {
    id: sceneId || `scene-${Math.random()}`,
    video_id: videoId,
    video_filename: videoFilename,
    index: 0,
    start_s: 0,
    end_s: 10,
  };
}

// Inline implementations (since we can't import TS modules in plain Node)
function shortId(uuid) {
  return uuid.slice(0, 8);
}

function groupScenesByVideo(scenes) {
  const grouped = new Map();

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

function filterScenesByToggles(scenes, toggles) {
  return scenes.filter((scene) => {
    const toggleState = toggles[scene.video_id];
    return toggleState !== false;
  });
}

function createInitialToggles(videoIds) {
  return Object.fromEntries(videoIds.map((id) => [id, true]));
}

function extractUniqueVideoIds(scenes) {
  return Array.from(new Set(scenes.map((scene) => scene.video_id)));
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
console.log('\n🧪 Running File Toggle Utils Tests\n');

// Test 1: groupScenesByVideo - basic grouping
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
  ];
  const result = groupScenesByVideo(scenes);

  assert(result.length === 2, 'groupScenesByVideo: should group into 2 files');
  assert(result[0].sceneCount === 2, 'groupScenesByVideo: first file should have 2 scenes');
  assert(result[1].sceneCount === 1, 'groupScenesByVideo: second file should have 1 scene');
  assert(result[0].filename === 'Video A.mp4', 'groupScenesByVideo: should preserve filename');
}

// Test 2: groupScenesByVideo - sorting by scene count
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
  ];
  const result = groupScenesByVideo(scenes);

  assert(result[0].videoId === 'video-2', 'groupScenesByVideo: should sort by count desc');
  assert(result[0].sceneCount === 3, 'groupScenesByVideo: highest count first');
}

// Test 3: groupScenesByVideo - sorting by filename when counts equal
{
  const scenes = [
    createMockScene('video-1', 'Zebra.mp4'),
    createMockScene('video-2', 'Apple.mp4'),
  ];
  const result = groupScenesByVideo(scenes);

  assert(result[0].filename === 'Apple.mp4', 'groupScenesByVideo: should sort alphabetically');
  assert(result[1].filename === 'Zebra.mp4', 'groupScenesByVideo: alphabetical order');
}

// Test 4: groupScenesByVideo - fallback label for missing filename
{
  const videoId = '12345678-1234-1234-1234-123456789abc';
  const scenes = [
    createMockScene(videoId, null),
  ];
  const result = groupScenesByVideo(scenes);

  assert(result[0].filename.startsWith('Untitled ('), 'groupScenesByVideo: fallback label starts with Untitled');
  assert(result[0].filename.includes('12345678'), 'groupScenesByVideo: fallback includes short ID');
}

// Test 5: filterScenesByToggles - show enabled files
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4', 'scene-1'),
    createMockScene('video-2', 'Video B.mp4', 'scene-2'),
  ];
  const toggles = { 'video-1': true, 'video-2': false };
  const result = filterScenesByToggles(scenes, toggles);

  assert(result.length === 1, 'filterScenesByToggles: should show only enabled file');
  assert(result[0].id === 'scene-1', 'filterScenesByToggles: should show scene from enabled video');
}

// Test 6: filterScenesByToggles - missing toggle key defaults to visible
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4', 'scene-1'),
    createMockScene('video-2', 'Video B.mp4', 'scene-2'),
  ];
  const toggles = { 'video-1': false };
  const result = filterScenesByToggles(scenes, toggles);

  assert(result.length === 1, 'filterScenesByToggles: missing key should default to visible');
  assert(result[0].id === 'scene-2', 'filterScenesByToggles: should show scene with missing toggle');
}

// Test 7: filterScenesByToggles - hide all
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
  ];
  const toggles = { 'video-1': false, 'video-2': false };
  const result = filterScenesByToggles(scenes, toggles);

  assert(result.length === 0, 'filterScenesByToggles: should hide all when all disabled');
}

// Test 8: createInitialToggles
{
  const videoIds = ['video-1', 'video-2', 'video-3'];
  const result = createInitialToggles(videoIds);

  assertEquals(result, { 'video-1': true, 'video-2': true, 'video-3': true }, 'createInitialToggles: should create all-enabled toggles');
}

// Test 9: extractUniqueVideoIds
{
  const scenes = [
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-1', 'Video A.mp4'),
    createMockScene('video-2', 'Video B.mp4'),
  ];
  const result = extractUniqueVideoIds(scenes);

  assert(result.length === 2, 'extractUniqueVideoIds: should extract unique IDs');
  assert(result.includes('video-1'), 'extractUniqueVideoIds: should include video-1');
  assert(result.includes('video-2'), 'extractUniqueVideoIds: should include video-2');
}

// Test 10: Integration test - complete flow
{
  const scenes = [
    createMockScene('video-1', 'Movie.mp4', 'scene-1'),
    createMockScene('video-1', 'Movie.mp4', 'scene-2'),
    createMockScene('video-2', 'Clip.mp4', 'scene-3'),
  ];

  // Extract unique IDs
  const videoIds = extractUniqueVideoIds(scenes);
  assert(videoIds.length === 2, 'Integration: extract unique IDs');

  // Create initial toggles
  const toggles = createInitialToggles(videoIds);
  assert(Object.keys(toggles).length === 2, 'Integration: create toggles');

  // Group files
  const files = groupScenesByVideo(scenes);
  assert(files.length === 2, 'Integration: group files');

  // Filter with all enabled
  let visible = filterScenesByToggles(scenes, toggles);
  assert(visible.length === 3, 'Integration: all visible initially');

  // Disable one file
  toggles['video-1'] = false;
  visible = filterScenesByToggles(scenes, toggles);
  assert(visible.length === 1, 'Integration: hide video-1 scenes');
  assert(visible[0].id === 'scene-3', 'Integration: only video-2 visible');
}

// Summary
console.log('\n' + '='.repeat(50));
console.log(`✅ Passed: ${testsPassed}`);
console.log(`❌ Failed: ${testsFailed}`);
console.log('='.repeat(50) + '\n');

if (testsFailed > 0) {
  process.exit(1);
}
