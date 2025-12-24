'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

interface VideoItem {
  id: string;
  filename: string | null;
  status: string;
  duration_s: number | null;
  updated_at: string;
  error_message: string | null;
}

interface SearchItem {
  query_text: string;
  created_at: string;
  latency_ms: number | null;
  results_count: number | null;
  video_id: string | null;
}

interface UserDetail {
  user_id: string;
  full_name: string;
  videos_total: number;
  videos_ready: number;
  hours_ready: number;
  last_activity: string | null;
  searches_7d: number;
  avg_latency_ms_7d: number | null;
  recent_videos: VideoItem[];
  recent_searches: SearchItem[];
}

export default function UserDetailPage() {
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const params = useParams();
  const userId = params.id as string;

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        const userData = await apiRequest<UserDetail>(`/admin/users/${userId}`);
        setUser(userData);
      } catch (err) {
        console.error('Failed to load user detail:', err);
        setError(err instanceof Error ? err.message : 'Failed to load user detail');
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [router, userId]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'READY':
        return 'text-green-600 bg-green-100';
      case 'PROCESSING':
        return 'text-blue-600 bg-blue-100';
      case 'FAILED':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16 flex items-center justify-center">
        <div className="text-lg text-gray-600">Loading user details...</div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16 flex items-center justify-center">
        <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-6">{error || 'User not found'}</p>
          <button
            onClick={() => router.push('/admin')}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Return to Admin Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/admin')}
            className="text-blue-600 hover:text-blue-800 mb-4 flex items-center gap-2"
          >
            ← Back to Admin Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{user.full_name}</h1>
          <p className="text-gray-600 mt-1">User ID: {user.user_id}</p>
        </div>

        {/* Summary Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Videos Processed</div>
            <div className="text-3xl font-bold text-gray-900">{user.videos_ready}</div>
            <div className="text-sm text-gray-500 mt-2">of {user.videos_total} total</div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Hours Processed</div>
            <div className="text-3xl font-bold text-gray-900">{user.hours_ready.toFixed(1)}</div>
            <div className="text-sm text-gray-500 mt-2">Total video hours</div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Recent Searches</div>
            <div className="text-3xl font-bold text-gray-900">{user.searches_7d}</div>
            <div className="text-sm text-gray-500 mt-2">Last 7 days</div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Avg Search Latency</div>
            <div className="text-3xl font-bold text-gray-900">
              {user.avg_latency_ms_7d ? user.avg_latency_ms_7d.toFixed(0) : '—'}
            </div>
            <div className="text-sm text-gray-500 mt-2">milliseconds</div>
          </div>
        </div>

        {/* Recent Videos */}
        <div className="bg-white rounded-lg shadow overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Videos ({user.recent_videos.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Filename
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Updated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Error
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {user.recent_videos.map((video) => (
                  <tr key={video.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {video.filename || 'Untitled'}
                      </div>
                      <div className="text-xs text-gray-500">{video.id.slice(0, 8)}...</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(video.status)}`}>
                        {video.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {video.duration_s ? `${(video.duration_s / 60).toFixed(1)} min` : '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(video.updated_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm text-red-600">
                      {video.error_message ? (
                        <div className="max-w-xs truncate" title={video.error_message}>
                          {video.error_message}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {user.recent_videos.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              No videos found
            </div>
          )}
        </div>

        {/* Recent Searches */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Searches ({user.recent_searches.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Query
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Latency
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Results
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {user.recent_searches.map((search, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900 max-w-md">
                        {search.query_text}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(search.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {search.latency_ms ? `${search.latency_ms}ms` : '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {search.results_count ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {user.recent_searches.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              No searches found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
