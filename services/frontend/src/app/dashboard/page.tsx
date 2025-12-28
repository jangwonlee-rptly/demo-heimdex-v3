'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { UserProfile, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import ReprocessModal from '@/components/ReprocessModal';
import VideoCard from '@/components/VideoCard';

export const dynamic = 'force-dynamic';

export default function DashboardPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'info' | 'error' } | null>(null);
  const [reprocessModal, setReprocessModal] = useState<{ isOpen: boolean; video: Video | null }>({
    isOpen: false,
    video: null,
  });
  const router = useRouter();
  const { t } = useLanguage();

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        const profileData = await apiRequest<UserProfile | null>('/me/profile');
        if (!profileData) {
          router.push('/onboarding');
          return;
        }
        setProfile(profileData);

        const videoData = await apiRequest<{ videos: Video[]; total: number }>('/videos');
        setVideos(videoData.videos);
      } catch (error) {
        console.error('Failed to load dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [router]);

  useEffect(() => {
    const channel = supabase
      .channel('videos-changes')
      .on<Video>(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'videos',
        },
        (payload: RealtimePostgresChangesPayload<Video>) => {
          const updatedVideo = payload.new as Video;
          const oldVideo = payload.old as Video;

          // Merge the update with existing video data to preserve fields
          // that might not be included in the real-time payload
          setVideos((currentVideos) =>
            currentVideos.map((video) =>
              video.id === updatedVideo.id ? { ...video, ...updatedVideo } : video
            )
          );

          if (oldVideo.status !== updatedVideo.status) {
            let message = '';
            let type: 'success' | 'info' | 'error' = 'info';

            if (updatedVideo.status === 'READY') {
              message = `${updatedVideo.filename || 'Video'} is ready!`;
              type = 'success';
            } else if (updatedVideo.status === 'PROCESSING') {
              message = `${updatedVideo.filename || 'Video'} is now processing...`;
              type = 'info';
            } else if (updatedVideo.status === 'FAILED') {
              message = `${updatedVideo.filename || 'Video'} processing failed`;
              type = 'error';
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
  }, []);

  const handleProcessVideo = async (videoId: string) => {
    try {
      await apiRequest(`/videos/${videoId}/process`, { method: 'POST' });
      const videoData = await apiRequest<{ videos: Video[]; total: number }>('/videos');
      setVideos(videoData.videos);
      setNotification({ message: t.dashboard.processingStarted, type: 'info' });
      setTimeout(() => setNotification(null), 5000);
    } catch (error) {
      console.error('Failed to process video:', error);
      setNotification({ message: t.dashboard.failedToProcess, type: 'error' });
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const handleOpenReprocessModal = (video: Video) => {
    setReprocessModal({ isOpen: true, video });
  };

  const handleCloseReprocessModal = () => {
    setReprocessModal({ isOpen: false, video: null });
  };

  const handleReprocessSuccess = async () => {
    const videoData = await apiRequest<{ videos: Video[]; total: number }>('/videos');
    setVideos(videoData.videos);
    setNotification({
      message: t.reprocess.success,
      type: 'success',
    });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleViewVideo = (videoId: string) => {
    router.push(`/videos/${videoId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 spinner" />
          <p className="text-surface-400">{t.common.loading}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-accent-cyan/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 left-1/4 w-[500px] h-[500px] bg-accent-violet/5 rounded-full blur-[120px]" />
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
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-surface-100 mb-1">{t.dashboard.title}</h1>
              <p className="text-surface-400">
                {t.dashboard.welcome}, <span className="text-accent-cyan">{profile?.full_name}</span>
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push('/upload')}
                className="btn btn-primary"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                {t.dashboard.uploadVideo}
              </button>
              <button
                onClick={() => router.push('/search')}
                className="btn btn-secondary"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                {t.dashboard.searchVideos}
              </button>
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="stat-card">
            <div className="stat-label">{t.dashboard.totalVideos}</div>
            <div className="stat-value">{videos.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t.dashboard.ready}</div>
            <div className="stat-value text-status-success">{videos.filter(v => v.status === 'READY').length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t.dashboard.processing}</div>
            <div className="stat-value text-status-info">{videos.filter(v => v.status === 'PROCESSING').length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t.dashboard.pending}</div>
            <div className="stat-value text-status-warning">{videos.filter(v => v.status === 'PENDING').length}</div>
          </div>
        </div>

        {/* Videos List */}
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-surface-100">{t.dashboard.yourVideos}</h2>
            <span className="text-sm text-surface-500">{videos.length} {t.dashboard.videos}</span>
          </div>

          {videos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
                  <line x1="7" y1="2" x2="7" y2="22" />
                  <line x1="17" y1="2" x2="17" y2="22" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <line x1="2" y1="7" x2="7" y2="7" />
                  <line x1="2" y1="17" x2="7" y2="17" />
                  <line x1="17" y1="17" x2="22" y2="17" />
                  <line x1="17" y1="7" x2="22" y2="7" />
                </svg>
              </div>
              <p className="empty-state-title">{t.dashboard.noVideos}</p>
              <p className="empty-state-description">{t.dashboard.uploadFirst}</p>
              <button
                onClick={() => router.push('/upload')}
                className="btn btn-primary mt-6"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                {t.dashboard.uploadFirstVideo}
              </button>
            </div>
          ) : (
            <div className="video-card-grid">
              {videos.map((video, index) => (
                <VideoCard
                  key={video.id}
                  video={video}
                  index={index}
                  onProcess={handleProcessVideo}
                  onView={handleViewVideo}
                  onReprocess={handleOpenReprocessModal}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Reprocess Modal */}
      {reprocessModal.video && (
        <ReprocessModal
          videoId={reprocessModal.video.id}
          videoName={reprocessModal.video.filename || `Video ${reprocessModal.video.id.substring(0, 8)}`}
          isOpen={reprocessModal.isOpen}
          onClose={handleCloseReprocessModal}
          onSuccess={handleReprocessSuccess}
        />
      )}
    </div>
  );
}
