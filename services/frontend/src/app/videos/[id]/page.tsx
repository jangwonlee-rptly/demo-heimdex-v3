'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { Video, VideoDetails, VideoScene } from '@/types';
import { useLanguage } from '@/lib/i18n';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import ReprocessModal from '@/components/ReprocessModal';

export const dynamic = 'force-dynamic';

/**
 * Format seconds into HH:MM:SS or MM:SS.
 *
 * @param {number} [seconds] - The duration in seconds.
 * @returns {string} Formatted duration string.
 */
function formatDuration(seconds?: number): string {
  if (!seconds) return 'N/A';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format seconds into MM:SS.
 *
 * @param {number} seconds - The timestamp in seconds.
 * @returns {string} Formatted timestamp string.
 */
function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format date string into localized date.
 *
 * @param {string} [dateString] - The ISO date string.
 * @returns {string} Formatted date string.
 */
function formatDate(dateString?: string): string {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Video details page.
 *
 * Displays comprehensive information about a video including metadata, full transcript,
 * and a scene-by-scene breakdown with visual summaries and transcript segments.
 *
 * @returns {JSX.Element} The video details page.
 */
export default function VideoDetailsPage() {
  const { t } = useLanguage();
  const [videoDetails, setVideoDetails] = useState<VideoDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTranscript, setExpandedTranscript] = useState(false);
  const [expandedSummary, setExpandedSummary] = useState(false);
  const [viewMode, setViewMode] = useState<'details' | 'transcript'>('details');
  const [selectedScene, setSelectedScene] = useState<VideoScene | null>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [reprocessModalOpen, setReprocessModalOpen] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const router = useRouter();
  const params = useParams();
  const videoId = params.id as string;

  // Fetch video details
  const fetchVideoDetails = async () => {
    try {
      const data = await apiRequest<VideoDetails>(`/videos/${videoId}/details`);
      setVideoDetails(data);
      return data;
    } catch (err: any) {
      console.error('Failed to load video details:', err);
      setError(err.message || 'Failed to load video details');
      return null;
    }
  };

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      await fetchVideoDetails();
      setLoading(false);
    };

    init();
  }, [router, videoId]);

  // Set up realtime subscription for video status updates
  useEffect(() => {
    const channel = supabase
      .channel(`video-${videoId}-changes`)
      .on<Video>(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'videos',
          filter: `id=eq.${videoId}`,
        },
        async (payload: RealtimePostgresChangesPayload<Video>) => {
          const updatedVideo = payload.new as Video;
          const oldVideo = payload.old as Video;

          // Show notification if status changed
          if (oldVideo.status !== updatedVideo.status) {
            let message = '';
            let type: 'success' | 'info' | 'error' = 'info';

            if (updatedVideo.status === 'READY') {
              message = t.reprocess.completed;
              type = 'success';
              // Refresh the full video details when processing completes
              await fetchVideoDetails();
            } else if (updatedVideo.status === 'PROCESSING') {
              message = t.reprocess.started;
              type = 'info';
              // Update just the video status in the current details
              setVideoDetails((prev) =>
                prev ? { ...prev, video: { ...prev.video, status: 'PROCESSING' } } : prev
              );
            } else if (updatedVideo.status === 'FAILED') {
              message = t.reprocess.failed;
              type = 'error';
              // Update the video status
              setVideoDetails((prev) =>
                prev ? { ...prev, video: { ...prev.video, status: 'FAILED', error_message: updatedVideo.error_message } } : prev
              );
            }

            if (message) {
              setNotification({ message, type });
              // Auto-dismiss notification after 5 seconds
              setTimeout(() => setNotification(null), 5000);
            }
          }
        }
      )
      .subscribe();

    // Cleanup subscription on unmount
    return () => {
      supabase.removeChannel(channel);
    };
  }, [videoId, t]);

  const handleSceneClick = (scene: VideoScene) => {
    setSelectedScene(scene);

    // Wait for video to load and seek to timestamp
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.currentTime = scene.start_s;
      }
    }, 100);
  };

  const handleReprocessSuccess = () => {
    // Show initial notification - the real-time subscription will handle
    // showing the completion notification when status changes to READY
    setNotification({
      message: t.reprocess.success,
      type: 'info',
    });
    setTimeout(() => setNotification(null), 5000);
    // Update video status to show it's pending reprocessing
    setVideoDetails((prev) =>
      prev ? { ...prev, video: { ...prev.video, status: 'PENDING' } } : prev
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="mt-4 text-gray-600">{t.videoDetails.loading}</p>
        </div>
      </div>
    );
  }

  if (error || !videoDetails) {
    return (
      <div className="min-h-screen p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-medium">{t.common.error}</p>
            <p className="text-sm mt-1">{error || t.videoDetails.notFound}</p>
          </div>
        </div>
      </div>
    );
  }

  const { video, full_transcript, scenes, total_scenes, reprocess_hint } = videoDetails;

  // Filter scenes by selected tag
  const filteredScenes = selectedTag
    ? scenes.filter(scene => scene.tags?.includes(selectedTag))
    : scenes;

  // Get all unique tags from all scenes
  const allTags = Array.from(
    new Set(scenes.flatMap(scene => scene.tags || []))
  ).sort();

  const handleTagClick = (tag: string) => {
    if (selectedTag === tag) {
      setSelectedTag(null); // Deselect if clicking the same tag
    } else {
      setSelectedTag(tag);
    }
  };

  return (
    <div className="min-h-screen p-6">
      {/* Notification Toast */}
      {notification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div
            className={`rounded-lg shadow-lg p-4 min-w-[300px] ${
              notification.type === 'success'
                ? 'bg-green-50 border border-green-200 text-green-800'
                : notification.type === 'error'
                ? 'bg-red-50 border border-red-200 text-red-800'
                : 'bg-blue-50 border border-blue-200 text-blue-800'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {notification.type === 'success' && (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                )}
                {notification.type === 'error' && (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                )}
                {notification.type === 'info' && (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                )}
                <p className="font-medium">{notification.message}</p>
              </div>
              <button
                onClick={() => setNotification(null)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {video.filename || `Video ${video.id.substring(0, 8)}`}
              </h1>
              <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                  video.status === 'READY' ? 'bg-green-100 text-green-800' :
                  video.status === 'PROCESSING' ? 'bg-blue-100 text-blue-800' :
                  video.status === 'FAILED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {video.status}
                </span>
                <span>{t.videoDetails.uploadedAt}: {formatDate(video.created_at)}</span>
              </div>
            </div>
            {/* Reprocess Button */}
            {(video.status === 'READY' || video.status === 'FAILED') && (
              <button
                onClick={() => setReprocessModalOpen(true)}
                className="btn btn-secondary"
              >
                {t.reprocess.button}
              </button>
            )}
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setViewMode('details')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'details'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Details
          </button>
          <button
            onClick={() => setViewMode('transcript')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'transcript'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Transcript View
          </button>
        </div>

        {/* Details View */}
        {viewMode === 'details' && (
          <>
            {/* Video Metadata Card */}
            <div className="card mb-6">
          <h2 className="text-xl font-semibold mb-4">{t.videoDetails.videoInfo}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">{t.dashboard.duration}</p>
              <p className="font-semibold">{formatDuration(video.duration_s)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">{t.dashboard.resolution}</p>
              <p className="font-semibold">
                {video.width && video.height ? `${video.width} × ${video.height}` : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Frame Rate</p>
              <p className="font-semibold">
                {video.frame_rate ? `${video.frame_rate.toFixed(2)} fps` : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">{t.videoDetails.scenes}</p>
              <p className="font-semibold">{total_scenes}</p>
            </div>
          </div>
          {video.video_created_at && (
            <div className="mt-4">
              <p className="text-sm text-gray-600">Original Creation Date</p>
              <p className="font-semibold">{formatDate(video.video_created_at)}</p>
            </div>
          )}
        </div>

        {/* Video Summary Card */}
        {video.video_summary && (
          <div className="card mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Video Summary</h2>
              <button
                onClick={() => setExpandedSummary(!expandedSummary)}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                {expandedSummary ? 'Collapse' : 'Expand'}
              </button>
            </div>
            <div className={`text-gray-700 leading-relaxed ${
              expandedSummary ? '' : 'max-h-40 overflow-hidden relative'
            }`}>
              <p className="whitespace-pre-wrap">{video.video_summary}</p>
              {!expandedSummary && (
                <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-white to-transparent"></div>
              )}
            </div>
          </div>
        )}

        {/* Reprocess Hint */}
        {reprocess_hint && (
          <div className="card mb-6 bg-blue-50 border border-blue-200">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-blue-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="text-sm text-blue-800">{reprocess_hint}</p>
              </div>
            </div>
          </div>
        )}

        {/* Full Transcript Card */}
        {full_transcript && (
          <div className="card mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">{t.videoDetails.transcript}</h2>
              <button
                onClick={() => setExpandedTranscript(!expandedTranscript)}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                {expandedTranscript ? 'Collapse' : 'Expand'}
              </button>
            </div>
            <div className={`text-gray-700 leading-relaxed ${
              expandedTranscript ? '' : 'max-h-40 overflow-hidden relative'
            }`}>
              <p className="whitespace-pre-wrap">{full_transcript}</p>
              {!expandedTranscript && (
                <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-white to-transparent"></div>
              )}
            </div>
          </div>
        )}

        {/* Scenes Section */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-4">Scene-by-Scene Breakdown</h2>
          <p className="text-gray-600 mb-2">
            Detailed analysis of {selectedTag ? filteredScenes.length : total_scenes} scenes {selectedTag && `with tag "${selectedTag}"`}
          </p>

          {/* Tag Filter */}
          {allTags.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-medium text-gray-700">Filter by tag:</span>
                {selectedTag && (
                  <button
                    onClick={() => setSelectedTag(null)}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Clear filter
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {allTags.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => handleTagClick(tag)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      selectedTag === tag
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Scene Cards */}
        <div className="space-y-6">
          {filteredScenes.map((scene) => (
            <div key={scene.id} className="card">
              <div className="flex flex-col md:flex-row gap-6">
                {/* Scene Thumbnail */}
                {scene.thumbnail_url && (
                  <div className="flex-shrink-0">
                    <img
                      src={scene.thumbnail_url}
                      alt={`Scene ${scene.index + 1}`}
                      className="w-full md:w-64 h-auto rounded-lg object-cover"
                    />
                  </div>
                )}

                {/* Scene Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {t.videoDetails.sceneNumber} {scene.index + 1}
                    </h3>
                    <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                      {formatTimestamp(scene.start_s)} - {formatTimestamp(scene.end_s)}
                    </span>
                  </div>

                  {/* Visual Summary */}
                  {scene.visual_summary && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.visualSummary}
                      </h4>
                      <p className="text-gray-700 leading-relaxed">
                        {scene.visual_summary}
                      </p>
                    </div>
                  )}

                  {/* Transcript Segment */}
                  {scene.transcript_segment && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.transcript}
                      </h4>
                      <p className="text-gray-600 italic leading-relaxed">
                        "{scene.transcript_segment}"
                      </p>
                    </div>
                  )}

                  {/* Visual Description (Rich Semantics) */}
                  {scene.visual_description && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.visualDescription}
                      </h4>
                      <p className="text-gray-700 leading-relaxed">
                        {scene.visual_description}
                      </p>
                    </div>
                  )}

                  {/* Visual Entities */}
                  {scene.visual_entities && scene.visual_entities.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.detectedEntities}
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {scene.visual_entities.map((entity, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {entity}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Visual Actions */}
                  {scene.visual_actions && scene.visual_actions.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.detectedActions}
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {scene.visual_actions.map((action, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"
                          >
                            {action}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {scene.tags && scene.tags.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        {t.videoDetails.tags}
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {scene.tags.map((tag, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleTagClick(tag)}
                            className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                              selectedTag === tag
                                ? 'bg-primary-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            {tag}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Scene Metadata */}
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>Duration: {(scene.end_s - scene.start_s).toFixed(1)}s</span>
                      <span>Scene ID: {scene.id.substring(0, 8)}</span>
                      {scene.sidecar_version && (
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">
                          {scene.sidecar_version}
                        </span>
                      )}
                      {scene.processing_stats?.visual_analysis_called && (
                        <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">
                          {t.videoDetails.aiAnalyzed}
                        </span>
                      )}
                    </div>
                    {/* Processing Stats (collapsible debug info) */}
                    {scene.processing_stats && (
                      <details className="mt-2">
                        <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                          {t.videoDetails.processingDetails}
                        </summary>
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600 grid grid-cols-2 gap-2">
                          <span>Transcript: {scene.processing_stats.transcript_length} chars</span>
                          <span>Search text: {scene.processing_stats.search_text_length} chars</span>
                          <span>Keyframes: {scene.processing_stats.keyframes_extracted}</span>
                          <span>Best frame: {scene.processing_stats.best_frame_found ? 'Yes' : 'No'}</span>
                          {scene.processing_stats.visual_analysis_skipped_reason && (
                            <span className="col-span-2 text-amber-600">
                              Skipped: {scene.processing_stats.visual_analysis_skipped_reason}
                            </span>
                          )}
                          {scene.embedding_metadata && (
                            <span className="col-span-2">
                              Embedding: {scene.embedding_metadata.model} ({scene.embedding_metadata.dimensions}d)
                            </span>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* No Scenes Message */}
        {filteredScenes.length === 0 && scenes.length > 0 && (
          <div className="card text-center py-12">
            <p className="text-gray-600">
              No scenes found with tag "{selectedTag}".
            </p>
            <button
              onClick={() => setSelectedTag(null)}
              className="mt-4 btn btn-secondary"
            >
              Clear filter
            </button>
          </div>
        )}
        {scenes.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-gray-600">
              {video.status === 'READY'
                ? t.videoDetails.noScenes
                : 'Video is still being processed. Scenes will appear once processing is complete.'}
            </p>
          </div>
        )}
          </>
        )}

        {/* Transcript View */}
        {viewMode === 'transcript' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Transcript List */}
            <div className="card max-h-[calc(100vh-300px)] overflow-y-auto">
              <h2 className="text-xl font-semibold mb-4">Transcript</h2>

              {scenes.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  <p>
                    {video.status === 'READY'
                      ? 'No transcript segments available'
                      : 'Video is still being processed. Transcript will appear once processing is complete.'}
                  </p>
                </div>
              )}

              {scenes.length > 0 && (
                <div className="space-y-3">
                  {scenes.map((scene) => (
                    <button
                      key={scene.id}
                      onClick={() => handleSceneClick(scene)}
                      className={`w-full text-left p-4 rounded-lg border transition-colors ${
                        selectedScene?.id === scene.id
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-primary-300'
                      }`}
                    >
                      <div className="flex gap-4">
                        {/* Timestamp */}
                        <div className="flex-shrink-0 w-24">
                          <div className="text-sm font-medium text-gray-700">
                            {formatTimestamp(scene.start_s)}
                          </div>
                          <div className="text-xs text-gray-500">
                            {formatTimestamp(scene.end_s)}
                          </div>
                        </div>

                        {/* Transcript Segment */}
                        <div className="flex-1 min-w-0">
                          {scene.transcript_segment && (
                            <p className="text-sm text-gray-700 line-clamp-2">
                              {scene.transcript_segment}
                            </p>
                          )}
                          {!scene.transcript_segment && (
                            <p className="text-sm text-gray-400 italic">
                              No transcript for this segment
                            </p>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Video Player */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4">Video Player</h2>

              {!selectedScene && (
                <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center text-gray-500">
                  <p>Select a transcript segment to watch</p>
                </div>
              )}

              {selectedScene && (
                <div className="space-y-4">
                  <video
                    ref={videoRef}
                    controls
                    className="w-full aspect-video bg-black rounded-lg"
                  >
                    <source
                      src={`${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/videos/${video.storage_path}`}
                      type="video/mp4"
                    />
                    Your browser does not support the video tag.
                  </video>

                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="font-medium mb-2">Scene {selectedScene.index + 1}</h3>
                    <p className="text-sm text-gray-600 mb-2">
                      Timestamp: {formatTimestamp(selectedScene.start_s)} - {formatTimestamp(selectedScene.end_s)}
                    </p>
                    {selectedScene.visual_summary && (
                      <div className="mb-3">
                        <p className="text-sm font-medium text-gray-700">Visual Description:</p>
                        <p className="text-sm text-gray-600">{selectedScene.visual_summary}</p>
                      </div>
                    )}
                    {selectedScene.transcript_segment && (
                      <div>
                        <p className="text-sm font-medium text-gray-700">Transcript:</p>
                        <p className="text-sm text-gray-600">{selectedScene.transcript_segment}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Reprocess Modal */}
      <ReprocessModal
        videoId={videoId}
        videoName={video.filename || `Video ${video.id.substring(0, 8)}`}
        isOpen={reprocessModalOpen}
        onClose={() => setReprocessModalOpen(false)}
        onSuccess={handleReprocessSuccess}
      />
    </div>
  );
}
