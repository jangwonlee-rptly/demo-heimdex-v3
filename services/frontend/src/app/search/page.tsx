'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import type { SearchResult, VideoScene, Video } from '@/types';
import { useLanguage } from '@/lib/i18n';

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
              <p className="text-surface-400 text-sm">Search your videos with natural language</p>
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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Search Results */}
          <div className="card flex flex-col max-h-[calc(100vh-280px)]">
            <h2 className="text-lg font-semibold text-surface-100 mb-4 flex-shrink-0">
              Results
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
                <p className="empty-state-title">Enter a search query</p>
                <p className="empty-state-description">
                  Search for anything in your videos using natural language
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
                  Try adjusting your search query
                </p>
              </div>
            )}

            {results && results.results.length > 0 && (
              <div className="space-y-3">
                {results.results.map((scene, index) => (
                  <button
                    key={scene.id}
                    onClick={() => handleSceneClick(scene)}
                    className={`scene-card w-full text-left ${
                      selectedScene?.id === scene.id ? 'active' : ''
                    }`}
                    style={{ animationDelay: `${index * 0.03}s` }}
                  >
                    <div className="flex gap-3">
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
                              {(scene.similarity * 100).toFixed(0)}% match
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
            <h2 className="text-lg font-semibold text-surface-100 mb-4">Video Player</h2>

            {!selectedScene && (
              <div className="video-container aspect-video flex items-center justify-center">
                <div className="text-center">
                  <svg className="w-12 h-12 text-surface-600 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  <p className="text-surface-500">Select a scene to watch</p>
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
                        Visual Description
                      </p>
                      <p className="text-sm text-surface-300">
                        {selectedScene.visual_description || selectedScene.visual_summary}
                      </p>
                    </div>
                  )}

                  {selectedScene.transcript_segment && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">
                        Transcript
                      </p>
                      <p className="text-sm text-surface-400 italic">
                        &quot;{selectedScene.transcript_segment}&quot;
                      </p>
                    </div>
                  )}

                  {selectedScene.visual_entities && selectedScene.visual_entities.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
                        Detected Entities
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
                        Detected Actions
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
                        Tags
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
