'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { SearchResult, VideoScene, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

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

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
      }
    };
    checkAuth();
  }, [router]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);

    try {
      const searchResults = await apiRequest<SearchResult>('/search', {
        method: 'POST',
        body: JSON.stringify({
          query: query.trim(),
          limit: 20,
          threshold: 0.2,
        }),
      });

      setResults(searchResults);
      setSelectedScene(null);
      setCurrentVideo(null);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  const handleSceneClick = async (scene: VideoScene) => {
    setSelectedScene(scene);

    // Load video details
    try {
      const video = await apiRequest<Video>(`/videos/${scene.video_id}`);
      setCurrentVideo(video);

      // Wait for video to load and seek to timestamp
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
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => router.push('/dashboard')}
            className="btn btn-secondary"
          >
            ← {t.common.back}
          </button>
          <LanguageToggle />
        </div>

        <div className="card mb-6">
          <h1 className="text-2xl font-bold mb-4">{t.search.title}</h1>

          <form onSubmit={handleSearch} className="flex gap-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.search.searchPlaceholder}
              className="input flex-1"
            />
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="btn btn-primary"
            >
              {searching ? t.search.searching : t.search.searchButton}
            </button>
          </form>

          {results && (
            <div className="mt-4 text-sm text-gray-600">
              {results.total} {t.search.resultsFound} ({results.latency_ms}ms)
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Search Results */}
          <div className="card max-h-[calc(100vh-300px)] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4">Results</h2>

            {!results && (
              <div className="text-center py-12 text-gray-500">
                <p>Enter a search query to find scenes in your videos</p>
              </div>
            )}

            {results && results.results.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p>{t.search.noResults}</p>
                <p className="text-sm mt-2">Try adjusting your search query</p>
              </div>
            )}

            {results && results.results.length > 0 && (
              <div className="space-y-3">
                {results.results.map((scene) => (
                  <button
                    key={scene.id}
                    onClick={() => handleSceneClick(scene)}
                    className={`w-full text-left p-4 rounded-lg border transition-colors ${
                      selectedScene?.id === scene.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex gap-3">
                      {scene.thumbnail_url && (
                        <img
                          src={scene.thumbnail_url}
                          alt="Scene thumbnail"
                          className="w-24 h-16 object-cover rounded"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-gray-500">
                            {t.search.scene} {scene.index + 1}
                          </span>
                          <span className="text-xs text-gray-400">
                            {scene.start_s.toFixed(1)}s - {scene.end_s.toFixed(1)}s
                          </span>
                          {scene.similarity && (
                            <span className="text-xs text-primary-600 font-medium">
                              {(scene.similarity * 100).toFixed(0)}% match
                            </span>
                          )}
                        </div>
                        {scene.visual_summary && (
                          <p className="text-sm text-gray-700 line-clamp-2 mb-1">
                            {scene.visual_summary}
                          </p>
                        )}
                        {scene.transcript_segment && (
                          <p className="text-xs text-gray-500 line-clamp-1">
                            &quot;{scene.transcript_segment}&quot;
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
                <p>Select a scene to watch</p>
              </div>
            )}

            {selectedScene && currentVideo && (
              <div className="space-y-4">
                <video
                  ref={videoRef}
                  controls
                  className="w-full aspect-video bg-black rounded-lg"
                >
                  <source
                    src={`${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/videos/${currentVideo.storage_path}`}
                    type="video/mp4"
                  />
                  Your browser does not support the video tag.
                </video>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h3 className="font-medium mb-2">{t.search.scene} {selectedScene.index + 1}</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    {t.search.timestamp}: {selectedScene.start_s.toFixed(1)}s - {selectedScene.end_s.toFixed(1)}s
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
                      <p className="text-sm text-gray-600">&quot;{selectedScene.transcript_segment}&quot;</p>
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
