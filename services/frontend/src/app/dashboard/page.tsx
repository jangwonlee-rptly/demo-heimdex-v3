'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { UserProfile, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

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
