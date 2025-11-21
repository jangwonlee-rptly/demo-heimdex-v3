'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { VideoDetails } from '@/types';

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
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function VideoDetailsPage() {
  const [videoDetails, setVideoDetails] = useState<VideoDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTranscript, setExpandedTranscript] = useState(false);
  const router = useRouter();
  const params = useParams();
  const videoId = params.id as string;

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        const data = await apiRequest<VideoDetails>(`/videos/${videoId}/details`);
        setVideoDetails(data);
      } catch (err: any) {
        console.error('Failed to load video details:', err);
        setError(err.message || 'Failed to load video details');
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [router, videoId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="mt-4 text-gray-600">Loading video details...</p>
        </div>
      </div>
    );
  }

  if (error || !videoDetails) {
    return (
      <div className="min-h-screen p-6">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => router.push('/dashboard')}
            className="btn btn-secondary mb-6"
          >
            ← Back to Dashboard
          </button>
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-medium">Error</p>
            <p className="text-sm mt-1">{error || 'Video not found'}</p>
          </div>
        </div>
      </div>
    );
  }

  const { video, full_transcript, scenes, total_scenes } = videoDetails;

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/dashboard')}
            className="btn btn-secondary mb-4"
          >
            ← Back to Dashboard
          </button>
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
            <span>Uploaded {formatDate(video.created_at)}</span>
          </div>
        </div>

        {/* Video Metadata Card */}
        <div className="card mb-6">
          <h2 className="text-xl font-semibold mb-4">Video Information</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">Duration</p>
              <p className="font-semibold">{formatDuration(video.duration_s)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Resolution</p>
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
              <p className="text-sm text-gray-600">Total Scenes</p>
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

        {/* Full Transcript Card */}
        {full_transcript && (
          <div className="card mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Full Transcript</h2>
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
          <p className="text-gray-600 mb-6">
            Detailed analysis of all {total_scenes} scenes detected in this video
          </p>
        </div>

        {/* Scene Cards */}
        <div className="space-y-6">
          {scenes.map((scene) => (
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
                      Scene {scene.index + 1}
                    </h3>
                    <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                      {formatTimestamp(scene.start_s)} - {formatTimestamp(scene.end_s)}
                    </span>
                  </div>

                  {/* Visual Summary */}
                  {scene.visual_summary && (
                    <div className="mb-4">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        Visual Description
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
                        Transcript
                      </h4>
                      <p className="text-gray-600 italic leading-relaxed">
                        "{scene.transcript_segment}"
                      </p>
                    </div>
                  )}

                  {/* Scene Metadata */}
                  <div className="flex items-center gap-4 text-xs text-gray-500 mt-4 pt-4 border-t border-gray-200">
                    <span>Duration: {(scene.end_s - scene.start_s).toFixed(1)}s</span>
                    <span>Scene ID: {scene.id.substring(0, 8)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* No Scenes Message */}
        {scenes.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-gray-600">
              {video.status === 'READY'
                ? 'No scenes detected in this video.'
                : 'Video is still being processed. Scenes will appear once processing is complete.'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
