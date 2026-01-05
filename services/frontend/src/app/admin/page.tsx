'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

interface AdminOverviewMetrics {
  videos_ready_total: number;
  videos_failed_total: number;
  videos_total: number;
  failure_rate_pct: number;
  hours_ready_total: number;
  searches_7d: number;
  avg_search_latency_ms_7d: number | null;
  searches_30d: number;
  avg_search_latency_ms_30d: number | null;
}

interface ThroughputDataPoint {
  day: string;
  videos_ready: number;
  hours_ready: number;
}

interface SearchDataPoint {
  day: string;
  searches: number;
  avg_latency_ms: number | null;
}

interface UserListItem {
  user_id: string;
  full_name: string;
  videos_total: number;
  videos_ready: number;
  hours_ready: number;
  last_activity: string | null;
  searches_7d: number;
  avg_latency_ms_7d: number | null;
}

export default function AdminPage() {
  const [overview, setOverview] = useState<AdminOverviewMetrics | null>(null);
  const [throughputData, setThroughputData] = useState<ThroughputDataPoint[]>([]);
  const [searchData, setSearchData] = useState<SearchDataPoint[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<'last_activity' | 'hours_ready' | 'videos_ready' | 'searches_7d'>('last_activity');
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessResult, setReprocessResult] = useState<{ success: boolean; message: string } | null>(null);
  const router = useRouter();

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        // Fetch all admin data in parallel
        const [overviewRes, throughputRes, searchRes, usersRes] = await Promise.all([
          apiRequest<AdminOverviewMetrics>('/admin/overview').catch(() => null),
          apiRequest<{ data: ThroughputDataPoint[] }>('/admin/timeseries/throughput?range=30d&bucket=day').catch(() => ({ data: [] })),
          apiRequest<{ data: SearchDataPoint[] }>('/admin/timeseries/search?range=30d&bucket=day').catch(() => ({ data: [] })),
          apiRequest<{ items: UserListItem[] }>(`/admin/users?range=7d&page=${page}&page_size=50&sort=${sortBy}`).catch(() => ({ items: [] })),
        ]);

        if (overviewRes) {
          setOverview(overviewRes);
          setThroughputData(throughputRes.data);
          setSearchData(searchRes.data);
          setUsers(usersRes.items);
        } else {
          setError('Not authorized. Admin access required.');
        }
      } catch (err) {
        console.error('Failed to load admin data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load admin data');
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [router, page, sortBy]);

  const handleUserClick = (userId: string) => {
    router.push(`/admin/users/${userId}`);
  };

  const handleReprocessAll = async () => {
    if (!confirm('Are you sure you want to reprocess ALL videos using the latest embedding methods? This will regenerate embeddings for all videos in the system. The process is idempotent and safe to re-run.')) {
      return;
    }

    setReprocessing(true);
    setReprocessResult(null);

    try {
      const result = await apiRequest<{
        status: string;
        spec_version: string;
        scope: string;
        video_count: number;
        message: string
      }>(
        '/admin/reprocess-embeddings',
        {
          method: 'POST',
          body: JSON.stringify({
            scope: 'all',
            force: false,
          }),
        }
      );
      setReprocessResult({
        success: true,
        message: `${result.message} (Spec: ${result.spec_version})`,
      });
    } catch (err) {
      setReprocessResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to trigger reprocessing',
      });
    } finally {
      setReprocessing(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16 flex items-center justify-center">
        <div className="text-lg text-gray-600">Loading admin dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16 flex items-center justify-center">
        <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Access Denied</h2>
          <p className="text-gray-700 mb-6">{error}</p>
          <button
            onClick={() => router.push('/dashboard')}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!overview) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8 flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
            <p className="text-gray-600 mt-2">System metrics and user analytics</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <button
              onClick={handleReprocessAll}
              disabled={reprocessing}
              className={`px-4 py-2 rounded-md text-white font-medium ${
                reprocessing
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-orange-600 hover:bg-orange-700'
              }`}
              title="Regenerate embeddings using the latest embedding methods"
            >
              {reprocessing ? 'Reprocessing...' : 'Reprocess Embeddings (All)'}
            </button>
            {reprocessResult && (
              <div
                className={`text-sm px-3 py-1 rounded ${
                  reprocessResult.success
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {reprocessResult.message}
              </div>
            )}
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Total Videos</div>
            <div className="text-3xl font-bold text-gray-900">{overview.videos_total.toLocaleString()}</div>
            <div className="text-sm text-gray-500 mt-2">
              {overview.videos_ready_total} ready, {overview.videos_failed_total} failed
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Success Rate</div>
            <div className="text-3xl font-bold text-green-600">
              {(100 - overview.failure_rate_pct).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-500 mt-2">
              {overview.failure_rate_pct.toFixed(1)}% failure rate
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Hours Processed</div>
            <div className="text-3xl font-bold text-gray-900">{overview.hours_ready_total.toFixed(1)}</div>
            <div className="text-sm text-gray-500 mt-2">Total video hours</div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Searches (7d)</div>
            <div className="text-3xl font-bold text-gray-900">{overview.searches_7d.toLocaleString()}</div>
            <div className="text-sm text-gray-500 mt-2">
              {overview.avg_search_latency_ms_7d ? `${overview.avg_search_latency_ms_7d.toFixed(0)}ms avg` : 'No data'}
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Throughput Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Processing Throughput (30 days)</h2>
            <div className="space-y-2">
              {throughputData.length > 0 ? (
                <>
                  <div className="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Date</span>
                    <span>Videos / Hours</span>
                  </div>
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {throughputData.slice(-14).map((point) => (
                      <div key={point.day} className="flex justify-between items-center py-1 text-sm">
                        <span className="text-gray-700">{point.day}</span>
                        <div className="text-right">
                          <span className="text-gray-900 font-medium">{point.videos_ready}</span>
                          <span className="text-gray-500 ml-2">/ {point.hours_ready.toFixed(1)}h</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-gray-500 text-center py-8">No throughput data available</div>
              )}
            </div>
          </div>

          {/* Search Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Search Activity (30 days)</h2>
            <div className="space-y-2">
              {searchData.length > 0 ? (
                <>
                  <div className="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Date</span>
                    <span>Searches / Latency</span>
                  </div>
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {searchData.slice(-14).map((point) => (
                      <div key={point.day} className="flex justify-between items-center py-1 text-sm">
                        <span className="text-gray-700">{point.day}</span>
                        <div className="text-right">
                          <span className="text-gray-900 font-medium">{point.searches}</span>
                          {point.avg_latency_ms && (
                            <span className="text-gray-500 ml-2">/ {point.avg_latency_ms.toFixed(0)}ms</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-gray-500 text-center py-8">No search data available</div>
              )}
            </div>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Users</h2>
          </div>
          <div className="px-6 py-4 border-b border-gray-200 flex gap-4">
            <label className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm"
              >
                <option value="last_activity">Last Activity</option>
                <option value="hours_ready">Hours Processed</option>
                <option value="videos_ready">Videos Processed</option>
                <option value="searches_7d">Recent Searches</option>
              </select>
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Videos
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Hours
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Searches (7d)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Activity
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user) => (
                  <tr
                    key={user.user_id}
                    onClick={() => handleUserClick(user.user_id)}
                    className="hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{user.full_name}</div>
                      <div className="text-xs text-gray-500">{user.user_id.slice(0, 8)}...</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.videos_ready}/{user.videos_total}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.hours_ready.toFixed(1)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.searches_7d}
                      {user.avg_latency_ms_7d && (
                        <span className="text-gray-500 ml-1">({user.avg_latency_ms_7d.toFixed(0)}ms)</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {user.last_activity ? new Date(user.last_activity).toLocaleDateString() : 'Never'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {users.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              No users found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
