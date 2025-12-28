'use client';

/**
 * Search Page.
 *
 * Provides semantic search interface for finding video scenes.
 * Features include:
 * - Natural language search query input
 * - Adjustable search weights and preferences
 * - Video file filtering
 * - Highlight reel builder (selection tray)
 * - Video player for previewing results
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { SearchResult, VideoScene, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';
import { SearchWeightControls, type Weights, type WeightState } from '@/components/SearchWeightControls';
import { FileToggleBar } from '@/components/FileToggleBar';
import { SelectionTray } from '@/components/SelectionTray';
import { HighlightJobStatus, type HighlightJob } from '@/components/HighlightJobStatus';
import {
  groupScenesByVideo,
  filterScenesByToggles,
  extractUniqueVideoIds,
  createInitialToggles,
} from '@/components/fileToggleUtils';
import {
  type SelectedScene,
  toSelectedScene,
  addSelected,
  removeSelected,
  reorderSelected,
  totalDuration,
  isSceneSelected,
  buildExportPayload,
} from '@/components/highlightReelUtils';

export const dynamic = 'force-dynamic';

export default function SearchPage() {
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [selectedScene, setSelectedScene] = useState<VideoScene | null>(null);
  const [currentVideo, setCurrentVideo] = useState<Video | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const router = useRouter();

  // Search weight state
  const [useSavedPreferences, setUseSavedPreferences] = useState(true);
  const [isOverride, setIsOverride] = useState(false);
  const [overrideWeights, setOverrideWeights] = useState<Weights | null>(null);

  // File toggle state
  const [fileToggles, setFileToggles] = useState<Record<string, boolean>>({});

  // Highlight reel selection state (persists across searches)
  const [selectedScenes, setSelectedScenes] = useState<SelectedScene[]>([]);
  const [isExporting, setIsExporting] = useState(false);
  const [highlightJob, setHighlightJob] = useState<HighlightJob | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
      }
    };
    checkAuth();
  }, [router]);

  const handleWeightChange = (state: WeightState) => {
    setUseSavedPreferences(state.useSaved);
    setIsOverride(state.isOverride);
    setOverrideWeights(state.isOverride ? state.weights : null);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);

    try {
      // Build search payload with weight configuration
      const payload: any = {
        query: query.trim(),
        limit: 20,
        threshold: 0.2,
        use_saved_preferences: useSavedPreferences,
      };

      // Only include channel_weights if user has overridden
      if (isOverride && overrideWeights) {
        payload.channel_weights = {
          transcript: overrideWeights.transcript,
          visual: overrideWeights.visual,
          summary: overrideWeights.summary,
          lexical: overrideWeights.lexical,
        };
      }

      const searchResults = await apiRequest<SearchResult>('/search', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setResults(searchResults);
      setSelectedScene(null);
      setCurrentVideo(null);

      // Reset file toggles with all files enabled
      const uniqueVideoIds = extractUniqueVideoIds(searchResults.results);
      setFileToggles(createInitialToggles(uniqueVideoIds));

      // Log weight source for debugging (if provided by backend)
      if (process.env.NODE_ENV === 'development' && searchResults.weight_source) {
        console.log('[Search] Weight source:', searchResults.weight_source);
        if (searchResults.fusion_weights) {
          console.log('[Search] Fusion weights:', searchResults.fusion_weights);
        }
      }
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  // Derived data for file toggles (memoized)
  const groupedFiles = useMemo(
    () => groupScenesByVideo(results?.results ?? []),
    [results]
  );

  const visibleScenes = useMemo(
    () => filterScenesByToggles(results?.results ?? [], fileToggles),
    [results, fileToggles]
  );

  // File toggle handlers
  const handleToggleFile = (videoId: string) => {
    setFileToggles((prev) => ({ ...prev, [videoId]: !prev[videoId] }));
  };

  const handleToggleAll = () => {
    const allEnabled = Object.fromEntries(
      groupedFiles.map((file) => [file.videoId, true])
    );
    setFileToggles(allEnabled);
  };

  const handleToggleNone = () => {
    const allDisabled = Object.fromEntries(
      groupedFiles.map((file) => [file.videoId, false])
    );
    setFileToggles(allDisabled);
  };

  // Highlight reel selection handlers
  const handleToggleSelection = (scene: VideoScene, e: React.MouseEvent) => {
    e.stopPropagation();
    const selectedScene = toSelectedScene(scene);
    if (isSceneSelected(selectedScenes, scene.id)) {
      setSelectedScenes(removeSelected(selectedScenes, scene.id));
    } else {
      setSelectedScenes(addSelected(selectedScenes, selectedScene));
    }
  };

  const handleRemoveFromSelection = (sceneId: string) => {
    setSelectedScenes(removeSelected(selectedScenes, sceneId));
  };

  const handleClearSelection = () => {
    setSelectedScenes([]);
  };

  const handleReorderSelection = (fromIndex: number, toIndex: number) => {
    setSelectedScenes(reorderSelected(selectedScenes, fromIndex, toIndex));
  };

  // Poll for job status updates
  const pollJobStatus = useCallback(async () => {
    if (!highlightJob?.job_id) return;

    try {
      const updatedJob = await apiRequest<HighlightJob>(`/highlights/jobs/${highlightJob.job_id}`);
      setHighlightJob(updatedJob);
    } catch (error) {
      console.error('[Highlight Export] Failed to poll job status:', error);
    }
  }, [highlightJob?.job_id]);

  const handleExportHighlights = async () => {
    if (selectedScenes.length === 0) return;

    setIsExporting(true);
    const payload = buildExportPayload(selectedScenes);

    try {
      const response = await apiRequest<{ job_id: string; status: string }>('/highlights/export', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      // Set initial job state and start polling
      setHighlightJob({
        job_id: response.job_id,
        status: response.status as 'queued',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });

      // Clear selection on successful export
      setSelectedScenes([]);
    } catch (error: any) {
      console.log('[Highlight Export] Payload:', payload);
      // Graceful fallback if endpoint doesn't exist
      if (error.message?.includes('404') || error.message?.includes('not found')) {
        alert(t.highlightReel?.exportNotAvailable || 'Export endpoint not available yet. Check console for payload.');
        console.log('[Highlight Export] Endpoint not available. Payload logged above.');
      } else {
        alert(`${t.highlightReel?.exportError || 'Export failed'}: ${error.message}`);
      }
    } finally {
      setIsExporting(false);
    }
  };

  const handleDismissJob = () => {
    setHighlightJob(null);
  };

  const handleRetryExport = () => {
    setHighlightJob(null);
    // User can reselect scenes and try again
  };

  const handleSceneClick = async (scene: VideoScene) => {
    setSelectedScene(scene);

    try {
      const video = await apiRequest<Video>(`/videos/${scene.video_id}`);
      setCurrentVideo(video);

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.currentTime = scene.start_s;
        }
      }, 500);
    } catch (error) {
      console.error('Failed to load video:', error);
    }
  };

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/3 w-[600px] h-[600px] bg-accent-cyan/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-accent-violet/5 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Search Weights Controls */}
        <SearchWeightControls onChange={handleWeightChange} className="mb-6" />

        {/* Search Header */}
        <div className="card mb-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-cyan/20 to-accent-violet/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-100">{t.search.title}</h1>
              <p className="text-surface-400 text-sm">{t.search.subtitle}</p>
            </div>
          </div>

          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t.search.searchPlaceholder}
                className="input pl-12"
              />
              <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="btn btn-primary"
            >
              {searching ? (
                <>
                  <div className="w-5 h-5 spinner" />
                  {t.search.searching}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  {t.search.searchButton}
                </>
              )}
            </button>
          </form>

          {results && (
            <div className="mt-4 flex items-center gap-4 text-sm">
              <span className="text-surface-300">
                <span className="font-semibold text-accent-cyan">{results.total}</span> {t.search.resultsFound}
              </span>
              <span className="text-surface-600">|</span>
              <span className="text-surface-500">{results.latency_ms}ms</span>
            </div>
          )}
        </div>

        {/* File Toggle Bar */}
        {results && results.results.length > 0 && (
          <FileToggleBar
            files={groupedFiles}
            toggles={fileToggles}
            onToggle={handleToggleFile}
            onAll={handleToggleAll}
            onNone={handleToggleNone}
            totalScenes={results.total}
            className="mb-6"
          />
        )}

        {/* Selection Tray for Highlight Reel */}
        <SelectionTray
          selected={selectedScenes}
          onRemove={handleRemoveFromSelection}
          onClear={handleClearSelection}
          onReorder={handleReorderSelection}
          onExport={handleExportHighlights}
          totalDurationS={totalDuration(selectedScenes)}
          isExporting={isExporting}
          className="mb-6"
        />

        {/* Highlight Job Status */}
        <HighlightJobStatus
          job={highlightJob}
          onPoll={pollJobStatus}
          onDismiss={handleDismissJob}
          onRetry={handleRetryExport}
          className="mb-6"
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Search Results */}
          <div className="card flex flex-col max-h-[calc(100vh-280px)]">
            <h2 className="text-lg font-semibold text-surface-100 mb-4 flex-shrink-0">
              {t.search.results}
            </h2>

            <div className="flex-1 overflow-y-auto no-scrollbar">
            {!results && (
              <div className="empty-state py-12">
                <div className="empty-state-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </div>
                <p className="empty-state-title">{t.search.enterQuery}</p>
                <p className="empty-state-description">
                  {t.search.enterQueryDescription}
                </p>
              </div>
            )}

            {results && results.results.length === 0 && (
              <div className="empty-state py-12">
                <div className="empty-state-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="8" y1="12" x2="16" y2="12" />
                  </svg>
                </div>
                <p className="empty-state-title">{t.search.noResults}</p>
                <p className="empty-state-description">
                  {t.search.tryAdjusting}
                </p>
              </div>
            )}

            {results && results.results.length > 0 && (
              <div className="space-y-3">
                {visibleScenes.length === 0 && (
                  <div className="empty-state py-12">
                    <div className="empty-state-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="8" y1="12" x2="16" y2="12" />
                      </svg>
                    </div>
                    <p className="empty-state-title">{t.search.allFilesHidden}</p>
                    <p className="empty-state-description">
                      {t.search.enableFiles}
                    </p>
                  </div>
                )}
                {visibleScenes.map((scene, index) => (
                  <button
                    key={scene.id}
                    onClick={() => handleSceneClick(scene)}
                    className={`scene-card w-full text-left ${
                      selectedScene?.id === scene.id ? 'active' : ''
                    }`}
                    style={{ animationDelay: `${index * 0.03}s` }}
                  >
                    <div className="flex gap-3">
                      {/* Selection Toggle */}
                      <div
                        onClick={(e) => handleToggleSelection(scene, e)}
                        className={`flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center cursor-pointer transition-all ${
                          isSceneSelected(selectedScenes, scene.id)
                            ? 'bg-accent-cyan border-accent-cyan text-surface-950'
                            : 'border-surface-600 hover:border-accent-cyan/50'
                        }`}
                        title={isSceneSelected(selectedScenes, scene.id)
                          ? (t.highlightReel?.removeFromSelection || 'Remove from selection')
                          : (t.highlightReel?.addToSelection || 'Add to selection')
                        }
                      >
                        {isSceneSelected(selectedScenes, scene.id) && (
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        )}
                      </div>
                      {scene.thumbnail_url && (
                        <div className="thumbnail w-28 h-[70px] flex-shrink-0">
                          <img
                            src={scene.thumbnail_url}
                            alt="Scene thumbnail"
                            className="w-full h-full"
                          />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-xs font-medium text-surface-400">
                            {t.search.scene} {scene.index + 1}
                          </span>
                          <span className="text-xs text-surface-600">
                            {scene.start_s.toFixed(1)}s - {scene.end_s.toFixed(1)}s
                          </span>
                          {scene.similarity && (
                            <span className="badge badge-accent text-[10px] py-0.5">
                              {(scene.similarity * 100).toFixed(0)}% {t.search.match}
                            </span>
                          )}
                        </div>
                        {scene.video_filename && (
                          <div className="mb-1.5">
                            <span
                              onClick={(e) => {
                                e.stopPropagation();
                                router.push(`/videos/${scene.video_id}`);
                              }}
                              className="text-xs text-accent-cyan hover:text-accent-cyan/80 hover:underline cursor-pointer inline-flex items-center gap-1"
                            >
                              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polygon points="5 3 19 12 5 21 5 3" />
                              </svg>
                              {scene.video_filename}
                            </span>
                          </div>
                        )}
                        {(scene.visual_description || scene.visual_summary) && (
                          <p className="text-sm text-surface-300 line-clamp-2 mb-1.5">
                            {scene.visual_description || scene.visual_summary}
                          </p>
                        )}
                        {scene.transcript_segment && (
                          <p className="text-xs text-surface-500 line-clamp-1 italic">
                            &quot;{scene.transcript_segment}&quot;
                          </p>
                        )}
                        {scene.tags && scene.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {scene.tags.slice(0, 4).map((tag, idx) => (
                              <span key={idx} className="tag text-[10px] py-0.5">
                                {tag}
                              </span>
                            ))}
                            {scene.tags.length > 4 && (
                              <span className="text-xs text-surface-600">
                                +{scene.tags.length - 4}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
            </div>
          </div>

          {/* Video Player */}
          <div className="card">
            <h2 className="text-lg font-semibold text-surface-100 mb-4">{t.search.videoPlayer}</h2>

            {!selectedScene && (
              <div className="video-container aspect-video flex items-center justify-center">
                <div className="text-center">
                  <svg className="w-12 h-12 text-surface-600 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  <p className="text-surface-500">{t.search.selectScene}</p>
                </div>
              </div>
            )}

            {selectedScene && currentVideo && (
              <div className="space-y-4">
                <div className="video-container">
                  <video
                    ref={videoRef}
                    controls
                    className="w-full aspect-video"
                  >
                    <source
                      src={`${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/videos/${currentVideo.storage_path}`}
                      type="video/mp4"
                    />
                    Your browser does not support the video tag.
                  </video>
                </div>

                <div className="p-4 rounded-xl bg-surface-800/50 border border-surface-700/30 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-surface-100">
                      {t.search.scene} {selectedScene.index + 1}
                    </h3>
                    <span className="text-sm text-surface-500">
                      {selectedScene.start_s.toFixed(1)}s - {selectedScene.end_s.toFixed(1)}s
                    </span>
                  </div>

                  {(selectedScene.visual_description || selectedScene.visual_summary) && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">
                        {t.search.visualDescription}
                      </p>
                      <p className="text-sm text-surface-300">
                        {selectedScene.visual_description || selectedScene.visual_summary}
                      </p>
                    </div>
                  )}

                  {selectedScene.transcript_segment && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">
                        {t.search.transcript}
                      </p>
                      <p className="text-sm text-surface-400 italic">
                        &quot;{selectedScene.transcript_segment}&quot;
                      </p>
                    </div>
                  )}

                  {selectedScene.visual_entities && selectedScene.visual_entities.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
                        {t.search.detectedEntities}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedScene.visual_entities.map((entity, idx) => (
                          <span key={idx} className="badge badge-info">
                            {entity}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedScene.visual_actions && selectedScene.visual_actions.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
                        {t.search.detectedActions}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedScene.visual_actions.map((action, idx) => (
                          <span key={idx} className="badge badge-success">
                            {action}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedScene.tags && selectedScene.tags.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
                        {t.search.tags}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedScene.tags.map((tag, idx) => (
                          <span key={idx} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
