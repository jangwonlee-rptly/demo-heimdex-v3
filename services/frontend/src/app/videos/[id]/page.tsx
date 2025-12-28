'use client';

/**
 * Video Details Page.
 *
 * Displays detailed information about a specific video, including:
 * - Metadata (duration, resolution, EXIF)
 * - Full transcript and summary
 * - Scene breakdown with visual descriptions
 * - Video player with scene seeking
 * - Controls for reprocessing and exporting scenes
 */

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { Video, VideoDetails, VideoScene } from '@/types';
import { useLanguage } from '@/lib/i18n';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import ReprocessModal from '@/components/ReprocessModal';
import ExportShortModal from '@/components/ExportShortModal';

export const dynamic = 'force-dynamic';

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

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateString?: string): string {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

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
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [sceneToExport, setSceneToExport] = useState<VideoScene | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [expandedTags, setExpandedTags] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const router = useRouter();
  const params = useParams();
  const videoId = params.id as string;

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

          if (oldVideo.status !== updatedVideo.status) {
            let message = '';
            let type: 'success' | 'info' | 'error' = 'info';

            if (updatedVideo.status === 'READY') {
              message = t.reprocess.completed;
              type = 'success';
              await fetchVideoDetails();
            } else if (updatedVideo.status === 'PROCESSING') {
              message = t.reprocess.started;
              type = 'info';
              setVideoDetails((prev) =>
                prev ? { ...prev, video: { ...prev.video, status: 'PROCESSING' } } : prev
              );
            } else if (updatedVideo.status === 'FAILED') {
              message = t.reprocess.failed;
              type = 'error';
              setVideoDetails((prev) =>
                prev ? { ...prev, video: { ...prev.video, status: 'FAILED', error_message: updatedVideo.error_message } } : prev
              );
            }

            if (message) {
              setNotification({ message, type });
              setTimeout(() => setNotification(null), 5000);
            }
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [videoId, t]);

  const handleSceneClick = (scene: VideoScene) => {
    setSelectedScene(scene);
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.currentTime = scene.start_s;
      }
    }, 100);
  };

  const handleReprocessSuccess = () => {
    setNotification({
      message: t.reprocess.success,
      type: 'info',
    });
    setTimeout(() => setNotification(null), 5000);
    setVideoDetails((prev) =>
      prev ? { ...prev, video: { ...prev.video, status: 'PENDING' } } : prev
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 spinner" />
          <p className="text-surface-400">{t.videoDetails.loading}</p>
        </div>
      </div>
    );
  }

  if (error || !videoDetails) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="card max-w-md text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-status-error/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-status-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <p className="text-lg font-medium text-surface-100 mb-2">{t.common.error}</p>
          <p className="text-surface-400 mb-6">{error || t.videoDetails.notFound}</p>
          <button onClick={() => router.push('/dashboard')} className="btn btn-primary">
            {t.videoDetails.goToDashboard}
          </button>
        </div>
      </div>
    );
  }

  const { video, full_transcript, scenes, total_scenes, reprocess_hint } = videoDetails;

  const filteredScenes = selectedTag
    ? scenes.filter(scene => scene.tags?.includes(selectedTag))
    : scenes;

  const allTags = Array.from(
    new Set(scenes.flatMap(scene => scene.tags || []))
  ).sort();

  const displayedTags = expandedTags ? allTags : allTags.slice(0, 15);

  const handleTagClick = (tag: string) => {
    setSelectedTag(selectedTag === tag ? null : tag);
  };

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-accent-cyan/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-1/4 left-1/4 w-[500px] h-[500px] bg-accent-violet/5 rounded-full blur-[120px]" />
      </div>

      {/* Notification Toast */}
      {notification && (
        <div className={`toast ${
          notification.type === 'success' ? 'toast-success' :
          notification.type === 'error' ? 'toast-error' : 'toast-info'
        }`}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              {notification.type === 'success' && (
                <div className="w-8 h-8 rounded-full bg-status-success/20 flex items-center justify-center">
                  <svg className="w-4 h-4 text-status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}
              {notification.type === 'error' && (
                <div className="w-8 h-8 rounded-full bg-status-error/20 flex items-center justify-center">
                  <svg className="w-4 h-4 text-status-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </div>
              )}
              {notification.type === 'info' && (
                <div className="w-8 h-8 rounded-full bg-accent-cyan/20 flex items-center justify-center">
                  <svg className="w-4 h-4 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                </div>
              )}
              <p className="font-medium text-surface-100">{notification.message}</p>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-surface-500 hover:text-surface-300 transition-colors"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button onClick={() => router.push('/dashboard')} className="btn btn-ghost p-2">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-surface-100 truncate">
              {video.filename || `Video ${video.id.substring(0, 8)}`}
            </h1>
            <div className="flex items-center gap-4 mt-1">
              <span className={`status-badge ${
                video.status === 'READY' ? 'status-ready' :
                video.status === 'PROCESSING' ? 'status-processing' :
                video.status === 'FAILED' ? 'status-failed' : 'status-pending'
              }`}>
                {video.status}
              </span>
              <span className="text-sm text-surface-500">{formatDate(video.created_at)}</span>
            </div>
          </div>
          {(video.status === 'READY' || video.status === 'FAILED') && (
            <button onClick={() => setReprocessModalOpen(true)} className="btn btn-secondary">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              {t.reprocess.button}
            </button>
          )}
        </div>

        {/* View Mode Toggle */}
        <div className="flex gap-1 mb-6 p-1 bg-surface-800/50 rounded-xl w-fit">
          <button
            onClick={() => setViewMode('details')}
            className={`py-2 px-6 rounded-lg text-sm font-medium transition-all ${
              viewMode === 'details'
                ? 'bg-surface-700 text-surface-100'
                : 'text-surface-400 hover:text-surface-200'
            }`}
          >
            {t.videoDetails.details}
          </button>
          <button
            onClick={() => setViewMode('transcript')}
            className={`py-2 px-6 rounded-lg text-sm font-medium transition-all ${
              viewMode === 'transcript'
                ? 'bg-surface-700 text-surface-100'
                : 'text-surface-400 hover:text-surface-200'
            }`}
          >
            {t.videoDetails.transcriptView}
          </button>
        </div>

        {/* Details View */}
        {viewMode === 'details' && (
          <>
            {/* Video Info Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="stat-card">
                <div className="stat-label">{t.dashboard.duration}</div>
                <div className="stat-value">{formatDuration(video.duration_s)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">{t.dashboard.resolution}</div>
                <div className="stat-value">{video.width && video.height ? `${video.width}x${video.height}` : 'N/A'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">{t.videoDetails.frameRate}</div>
                <div className="stat-value">{video.frame_rate ? `${video.frame_rate.toFixed(0)} fps` : 'N/A'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">{t.videoDetails.scenes}</div>
                <div className="stat-value">{total_scenes}</div>
              </div>
            </div>

            {/* EXIF Metadata Section */}
            {(video.location_latitude || video.camera_make || video.camera_model || video.exif_metadata) && (
              <div className="card mb-6">
                <h2 className="text-lg font-semibold text-surface-100 mb-4">{t.videoDetails.recordingInfo}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {/* Location */}
                  {(video.location_latitude || video.location_name) && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-700/30">
                      <div className="w-10 h-10 rounded-lg bg-accent-cyan/10 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                          <circle cx="12" cy="10" r="3" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">{t.videoDetails.location}</p>
                        {video.location_name ? (
                          <p className="text-surface-200 font-medium">{video.location_name}</p>
                        ) : null}
                        {video.location_latitude && video.location_longitude && (
                          <p className="text-sm text-surface-400">
                            {video.location_latitude.toFixed(6)}, {video.location_longitude.toFixed(6)}
                          </p>
                        )}
                        {video.exif_metadata?.gps?.altitude && (
                          <p className="text-xs text-surface-500">Altitude: {video.exif_metadata.gps.altitude.toFixed(1)}m</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Camera */}
                  {(video.camera_make || video.camera_model) && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-700/30">
                      <div className="w-10 h-10 rounded-lg bg-accent-violet/10 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-accent-violet" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                          <circle cx="12" cy="13" r="4" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">{t.videoDetails.camera}</p>
                        <p className="text-surface-200 font-medium">
                          {video.camera_make && video.camera_model
                            ? `${video.camera_make} ${video.camera_model}`
                            : video.camera_make || video.camera_model}
                        </p>
                        {video.exif_metadata?.camera?.software && (
                          <p className="text-xs text-surface-500">Software: {video.exif_metadata.camera.software}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Recording Date */}
                  {video.video_created_at && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-700/30">
                      <div className="w-10 h-10 rounded-lg bg-status-success/10 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                          <line x1="16" y1="2" x2="16" y2="6" />
                          <line x1="8" y1="2" x2="8" y2="6" />
                          <line x1="3" y1="10" x2="21" y2="10" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">{t.videoDetails.recorded}</p>
                        <p className="text-surface-200 font-medium">{formatDate(video.video_created_at)}</p>
                        <p className="text-xs text-surface-500">
                          {new Date(video.video_created_at).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Recording Settings (if available) */}
                  {video.exif_metadata?.recording && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-700/30">
                      <div className="w-10 h-10 rounded-lg bg-status-warning/10 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-status-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="3" />
                          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">{t.videoDetails.settings}</p>
                        <div className="flex flex-wrap gap-2 mt-1">
                          {video.exif_metadata.recording.iso && (
                            <span className="text-xs px-2 py-0.5 rounded bg-surface-600/50 text-surface-300">
                              ISO {video.exif_metadata.recording.iso}
                            </span>
                          )}
                          {video.exif_metadata.recording.aperture && (
                            <span className="text-xs px-2 py-0.5 rounded bg-surface-600/50 text-surface-300">
                              f/{video.exif_metadata.recording.aperture}
                            </span>
                          )}
                          {video.exif_metadata.recording.focal_length && (
                            <span className="text-xs px-2 py-0.5 rounded bg-surface-600/50 text-surface-300">
                              {video.exif_metadata.recording.focal_length}mm
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Video Summary */}
            {video.video_summary && (
              <div className="card mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-surface-100">{t.videoDetails.videoSummary}</h2>
                  <button
                    onClick={() => setExpandedSummary(!expandedSummary)}
                    className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                  >
                    {expandedSummary ? t.videoDetails.collapse : t.videoDetails.expand}
                  </button>
                </div>
                <div className={`relative ${!expandedSummary ? 'max-h-24 overflow-hidden' : ''}`}>
                  <p className="text-surface-300 leading-relaxed whitespace-pre-wrap">{video.video_summary}</p>
                  {!expandedSummary && (
                    <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-surface-800 to-transparent" />
                  )}
                </div>
              </div>
            )}

            {/* Reprocess Hint */}
            {reprocess_hint && (
              <div className="p-4 rounded-xl bg-accent-cyan/10 border border-accent-cyan/20 mb-6">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-accent-cyan flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                  <p className="text-sm text-surface-300">{reprocess_hint}</p>
                </div>
              </div>
            )}

            {/* Full Transcript */}
            {full_transcript && (
              <div className="card mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-surface-100">{t.videoDetails.transcript}</h2>
                  <button
                    onClick={() => setExpandedTranscript(!expandedTranscript)}
                    className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                  >
                    {expandedTranscript ? t.videoDetails.collapse : t.videoDetails.expand}
                  </button>
                </div>
                <div className={`relative ${!expandedTranscript ? 'max-h-24 overflow-hidden' : ''}`}>
                  <p className="text-surface-300 leading-relaxed whitespace-pre-wrap">{full_transcript}</p>
                  {!expandedTranscript && (
                    <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-surface-800 to-transparent" />
                  )}
                </div>
              </div>
            )}

            {/* Tag Filter */}
            {allTags.length > 0 && (
              <div className="card mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-surface-100">
                    {t.videoDetails.allTags}
                    <span className="ml-2 text-sm font-normal text-surface-500">({allTags.length})</span>
                  </h2>
                  {selectedTag && (
                    <button
                      onClick={() => setSelectedTag(null)}
                      className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                    >
                      {t.videoDetails.clearFilter}
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {displayedTags.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => handleTagClick(tag)}
                      className={`tag ${selectedTag === tag ? 'active' : ''}`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
                {allTags.length > 15 && (
                  <button
                    onClick={() => setExpandedTags(!expandedTags)}
                    className="mt-3 text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                  >
                    {expandedTags ? 'Show less' : `Show all ${allTags.length} tags`}
                  </button>
                )}
              </div>
            )}

            {/* Scenes */}
            <div className="mb-6">
              <h2 className="text-xl font-bold text-surface-100 mb-4">
                {t.videoDetails.sceneBreakdown}
                <span className="ml-2 text-sm font-normal text-surface-500">
                  ({selectedTag ? `${filteredScenes.length} ${t.videoDetails.filtered}` : total_scenes} {t.videoDetails.scenes})
                </span>
              </h2>
            </div>

            <div className="space-y-4">
              {filteredScenes.map((scene, idx) => (
                <div key={scene.id} className="card card-hover">
                  <div className="flex flex-col md:flex-row gap-6">
                    {scene.thumbnail_url && (
                      <div className="thumbnail w-full md:w-56 h-32 flex-shrink-0">
                        <img src={scene.thumbnail_url} alt={`Scene ${scene.index + 1}`} className="w-full h-full" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-surface-100">
                          {t.videoDetails.sceneNumber} {scene.index + 1}
                        </h3>
                        <span className="text-sm text-surface-500 bg-surface-700/50 px-3 py-1 rounded-full">
                          {formatTimestamp(scene.start_s)} - {formatTimestamp(scene.end_s)}
                        </span>
                      </div>

                      {scene.visual_summary && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">{t.videoDetails.visualSummary}</p>
                          <p className="text-surface-300">{scene.visual_summary}</p>
                        </div>
                      )}

                      {scene.transcript_segment && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">{t.videoDetails.transcript}</p>
                          <p className="text-surface-400 italic">&quot;{scene.transcript_segment}&quot;</p>
                        </div>
                      )}

                      {scene.visual_entities && scene.visual_entities.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">{t.videoDetails.detectedEntities}</p>
                          <div className="flex flex-wrap gap-1.5">
                            {scene.visual_entities.map((entity, i) => (
                              <span key={i} className="badge badge-info">{entity}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {scene.visual_actions && scene.visual_actions.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">{t.videoDetails.detectedActions}</p>
                          <div className="flex flex-wrap gap-1.5">
                            {scene.visual_actions.map((action, i) => (
                              <span key={i} className="badge badge-success">{action}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {scene.tags && scene.tags.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">{t.videoDetails.tags}</p>
                          <div className="flex flex-wrap gap-1.5">
                            {scene.tags.slice(0, 8).map((tag, i) => (
                              <button key={i} onClick={() => handleTagClick(tag)} className={`tag ${selectedTag === tag ? 'active' : ''}`}>
                                {tag}
                              </button>
                            ))}
                            {scene.tags.length > 8 && (
                              <span className="text-xs text-surface-600">+{scene.tags.length - 8}</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {filteredScenes.length === 0 && scenes.length > 0 && (
              <div className="empty-state">
                <p className="empty-state-title">{t.videoDetails.noScenesWithTag} &quot;{selectedTag}&quot;</p>
                <button onClick={() => setSelectedTag(null)} className="btn btn-secondary mt-4">{t.videoDetails.clearFilter}</button>
              </div>
            )}

            {scenes.length === 0 && (
              <div className="empty-state">
                <p className="empty-state-title">
                  {video.status === 'READY' ? t.videoDetails.noScenes : t.videoDetails.processingInProgress}
                </p>
              </div>
            )}
          </>
        )}

        {/* Transcript View */}
        {viewMode === 'transcript' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Transcript Panel - Refactored for proper header/list separation */}
            <div className="card flex flex-col h-[calc(100vh-280px)]">
              {/* Non-scrolling Header */}
              <div className="flex-shrink-0 pb-4 border-b border-surface-700/30">
                <h2 className="text-lg font-semibold text-surface-100">
                  {t.videoDetails.transcriptSegments}
                </h2>
              </div>

              {/* Scrollable Content Area */}
              <div className="flex-1 overflow-y-auto no-scrollbar pt-4">
                {scenes.length === 0 ? (
                  <div className="empty-state py-8">
                    <p className="empty-state-title">{t.videoDetails.noTranscript}</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {scenes.map((scene) => {
                      const sceneDuration = scene.end_s - scene.start_s;
                      const canExport = sceneDuration <= 180; // YouTube Shorts max duration

                      return (
                        <div
                          key={scene.id}
                          className={`scene-card ${selectedScene?.id === scene.id ? 'active' : ''}`}
                        >
                          <button
                            onClick={() => handleSceneClick(scene)}
                            className="w-full text-left"
                          >
                            <div className="flex gap-4">
                              <div className="flex-shrink-0 w-20">
                                <div className="text-sm font-medium text-accent-cyan">{formatTimestamp(scene.start_s)}</div>
                                <div className="text-xs text-surface-600">{formatTimestamp(scene.end_s)}</div>
                                <div className="text-xs text-surface-500 mt-1">{sceneDuration.toFixed(0)}s</div>
                              </div>
                              <div className="flex-1 min-w-0">
                                {scene.transcript_segment ? (
                                  <p className="text-sm text-surface-300 line-clamp-2">{scene.transcript_segment}</p>
                                ) : (
                                  <p className="text-sm text-surface-600 italic">{t.videoDetails.noTranscriptShort}</p>
                                )}
                              </div>
                            </div>
                          </button>

                          {/* Export Button */}
                          <div className="mt-3 pt-3 border-t border-surface-700/50">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSceneToExport(scene);
                                setExportModalOpen(true);
                              }}
                              disabled={!canExport}
                              className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                canExport
                                  ? 'bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20'
                                  : 'bg-surface-700/50 text-surface-500 cursor-not-allowed'
                              }`}
                              title={!canExport ? t.export.exceedsMax : t.export.title}
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                              {canExport ? t.videoDetails.exportToShort : `${t.videoDetails.tooLong} (${sceneDuration.toFixed(0)}s)`}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <h2 className="text-lg font-semibold text-surface-100 mb-4">{t.search.videoPlayer}</h2>

              {!selectedScene ? (
                <div className="video-container aspect-video flex items-center justify-center">
                  <div className="text-center">
                    <svg className="w-12 h-12 text-surface-600 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    <p className="text-surface-500">{t.videoDetails.selectSegment}</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="video-container">
                    <video ref={videoRef} controls className="w-full aspect-video">
                      <source
                        src={`${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/videos/${video.storage_path}`}
                        type="video/mp4"
                      />
                    </video>
                  </div>
                  <div className="p-4 rounded-xl bg-surface-800/50 border border-surface-700/30">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-surface-100">{t.search.scene} {selectedScene.index + 1}</h3>
                      <span className="text-sm text-surface-500">
                        {formatTimestamp(selectedScene.start_s)} - {formatTimestamp(selectedScene.end_s)}
                      </span>
                    </div>
                    {selectedScene.visual_summary && (
                      <div className="mb-3">
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">{t.videoDetails.visual}</p>
                        <p className="text-sm text-surface-300">{selectedScene.visual_summary}</p>
                      </div>
                    )}
                    {selectedScene.transcript_segment && (
                      <div>
                        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">{t.videoDetails.transcript}</p>
                        <p className="text-sm text-surface-400 italic">&quot;{selectedScene.transcript_segment}&quot;</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <ReprocessModal
        videoId={videoId}
        videoName={video.filename || `Video ${video.id.substring(0, 8)}`}
        isOpen={reprocessModalOpen}
        onClose={() => setReprocessModalOpen(false)}
        onSuccess={handleReprocessSuccess}
      />

      {sceneToExport && (
        <ExportShortModal
          scene={sceneToExport}
          isOpen={exportModalOpen}
          onClose={() => {
            setExportModalOpen(false);
            setSceneToExport(null);
          }}
        />
      )}
    </div>
  );
}
