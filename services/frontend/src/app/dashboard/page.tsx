'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { UserProfile, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';

export const dynamic = 'force-dynamic';

/**
 * User dashboard component.
 *
 * Displays the user's profile, uploaded videos, and quick actions.
 * Handles initial data fetching and redirection for unauthenticated users or users without profiles.
 *
 * @returns {JSX.Element} The dashboard page.
 */
export default function DashboardPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'info' | 'error' } | null>(null);
  const router = useRouter();
  const { t } = useLanguage();

  useEffect(() => {
    const init = async () => {
      // Check authentication
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        // Check if profile exists
        const profileData = await apiRequest<UserProfile | null>('/me/profile');

        if (!profileData) {
          // No profile, redirect to onboarding
          router.push('/onboarding');
          return;
        }

        setProfile(profileData);

        // Load videos
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

  // Set up realtime subscription for video status updates
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

          // Update the videos list with the new data
          setVideos((currentVideos) =>
            currentVideos.map((video) =>
              video.id === updatedVideo.id ? updatedVideo : video
            )
          );

          // Show notification if status changed
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
  }, []);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push('/login');
  };

  const handleProcessVideo = async (videoId: string) => {
    try {
      await apiRequest(`/videos/${videoId}/process`, { method: 'POST' });
      // Reload videos after triggering processing
      const videoData = await apiRequest<{ videos: Video[]; total: number }>('/videos');
      setVideos(videoData.videos);
      alert('Video processing started!');
    } catch (error) {
      console.error('Failed to process video:', error);
      alert('Failed to start processing');
    }
  };

  const getStatusBadge = (status: Video['status']) => {
    const styles: Record<string, string> = {
      PENDING: 'bg-yellow-100 text-yellow-800',
      PROCESSING: 'bg-blue-100 text-blue-800',
      READY: 'bg-green-100 text-green-800',
      FAILED: 'bg-red-100 text-red-800',
    };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status]}`}>
        {t.dashboard.status[status]}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">{t.common.loading}</div>
      </div>
    );
  }

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
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">{t.dashboard.title}</h1>
            <p className="text-gray-600 mt-1">
              {t.dashboard.welcome}, {profile?.full_name}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <LanguageToggle />
            <button
              onClick={handleSignOut}
              className="btn btn-secondary"
            >
              {t.common.signOut}
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4 mb-8">
          <button
            onClick={() => router.push('/upload')}
            className="btn btn-primary"
          >
            {t.dashboard.uploadVideo}
          </button>
          <button
            onClick={() => router.push('/search')}
            className="btn btn-secondary"
          >
            {t.dashboard.searchVideos}
          </button>
        </div>

        {/* Videos List */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4">{t.dashboard.yourVideos}</h2>

          {videos.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p className="text-lg mb-2">{t.dashboard.noVideos}</p>
              <p>{t.dashboard.uploadFirst}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {videos.map((video) => (
                <div
                  key={video.id}
                  className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-medium">
                          {video.filename || `Video ${video.id.substring(0, 8)}`}
                        </h3>
                        {getStatusBadge(video.status)}
                      </div>

                      <div className="text-sm text-gray-600 space-y-1">
                        {video.duration_s && (
                          <p>{t.dashboard.duration}: {Math.round(video.duration_s)}s</p>
                        )}
                        {video.width && video.height && (
                          <p>{t.dashboard.resolution}: {video.width}x{video.height}</p>
                        )}
                        <p>{t.dashboard.uploaded}: {new Date(video.created_at).toLocaleString()}</p>
                      </div>

                      {video.error_message && (
                        <p className="text-sm text-red-600 mt-2">
                          {t.dashboard.error}: {video.error_message}
                        </p>
                      )}

                      <div className="flex gap-2 mt-3">
                        {video.status === 'PENDING' && (
                          <button
                            onClick={() => handleProcessVideo(video.id)}
                            className="btn btn-primary btn-sm"
                          >
                            {t.dashboard.startProcessing}
                          </button>
                        )}
                        {video.status === 'READY' && (
                          <button
                            onClick={() => router.push(`/videos/${video.id}`)}
                            className="btn btn-primary btn-sm"
                          >
                            {t.dashboard.viewDetails}
                          </button>
                        )}
                      </div>
                    </div>

                    {video.thumbnail_url && (
                      <img
                        src={video.thumbnail_url}
                        alt="Video thumbnail"
                        className="w-32 h-20 object-cover rounded"
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
