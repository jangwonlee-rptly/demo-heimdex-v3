'use client';

import type { Video } from '@/types';
import { useLanguage } from '@/lib/i18n';

interface VideoCardProps {
  video: Video;
  onProcess?: (videoId: string) => void;
  onView?: (videoId: string) => void;
  onReprocess?: (video: Video) => void;
  index?: number;
}

export default function VideoCard({ video, onProcess, onView, onReprocess, index = 0 }: VideoCardProps) {
  const { t } = useLanguage();

  const getStatusBadge = (status: Video['status']) => {
    const styles: Record<string, string> = {
      PENDING: 'status-pending',
      PROCESSING: 'status-processing',
      READY: 'status-ready',
      FAILED: 'status-failed',
    };

    return (
      <span className={`status-badge ${styles[status]}`}>
        {status === 'PROCESSING' && (
          <svg className="w-3 h-3 mr-1 animate-spin inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
        )}
        {t.dashboard.status[status]}
      </span>
    );
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins > 0) {
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    return `${secs}s`;
  };

  return (
    <div
      className="video-card group"
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      {/* Thumbnail Container */}
      <div className="video-card-thumbnail">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.filename || 'Video thumbnail'}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-surface-800">
            <svg className="w-12 h-12 text-surface-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
        )}

        {/* Duration Badge */}
        {video.duration_s && (
          <div className="video-card-duration">
            {formatDuration(video.duration_s)}
          </div>
        )}

        {/* Status Overlay for Processing */}
        {video.status === 'PROCESSING' && (
          <div className="video-card-processing-overlay">
            <div className="w-8 h-8 spinner" />
          </div>
        )}

        {/* Hover Overlay */}
        <div className="video-card-hover-overlay">
          {video.status === 'READY' && onView && (
            <button
              onClick={(e) => { e.stopPropagation(); onView(video.id); }}
              className="video-card-play-btn"
            >
              <svg className="w-8 h-8" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </button>
          )}
          {video.status === 'PENDING' && onProcess && (
            <button
              onClick={(e) => { e.stopPropagation(); onProcess(video.id); }}
              className="video-card-play-btn"
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Card Content */}
      <div className="video-card-content">
        {/* Title Row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="video-card-title">
            {video.filename || `Video ${video.id.substring(0, 8)}`}
          </h3>
          {getStatusBadge(video.status)}
        </div>

        {/* Metadata Row */}
        <div className="video-card-meta">
          {video.width && video.height && (
            <span className="video-card-meta-item">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
              {video.height}p
            </span>
          )}
          <span className="video-card-meta-item">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            {new Date(video.created_at).toLocaleDateString()}
          </span>
        </div>

        {/* EXIF Metadata Row (Location & Camera) */}
        {(video.location_name || video.location_latitude || video.camera_make || video.camera_model) && (
          <div className="video-card-meta mt-1">
            {/* Show location name if available, otherwise show coordinates */}
            {(video.location_name || video.location_latitude) && (
              <span
                className="video-card-meta-item"
                title={video.location_latitude && video.location_longitude
                  ? `GPS: ${video.location_latitude.toFixed(4)}, ${video.location_longitude.toFixed(4)}`
                  : undefined}
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                {video.location_name
                  ? video.location_name
                  : `${video.location_latitude?.toFixed(2)}, ${video.location_longitude?.toFixed(2)}`}
              </span>
            )}
            {(video.camera_make || video.camera_model) && (
              <span className="video-card-meta-item">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                  <circle cx="12" cy="13" r="4" />
                </svg>
                {video.camera_make && video.camera_model
                  ? `${video.camera_make} ${video.camera_model}`
                  : video.camera_make || video.camera_model}
              </span>
            )}
          </div>
        )}

        {/* Error Message */}
        {video.error_message && (
          <p className="video-card-error">
            <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="truncate">{video.error_message}</span>
          </p>
        )}

        {/* Action Buttons */}
        <div className="video-card-actions">
          {video.status === 'PENDING' && onProcess && (
            <button
              onClick={() => onProcess(video.id)}
              className="btn btn-primary btn-sm w-full"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              {t.dashboard.startProcessing}
            </button>
          )}
          {video.status === 'READY' && (
            <div className="flex gap-2 w-full">
              {onView && (
                <button
                  onClick={() => onView(video.id)}
                  className="btn btn-primary btn-sm flex-1"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  {t.dashboard.viewDetails}
                </button>
              )}
              {onReprocess && (
                <button
                  onClick={() => onReprocess(video)}
                  className="btn btn-secondary btn-sm"
                  title={t.reprocess.button}
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="23 4 23 10 17 10" />
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                </button>
              )}
            </div>
          )}
          {video.status === 'FAILED' && onReprocess && (
            <button
              onClick={() => onReprocess(video)}
              className="btn btn-secondary btn-sm w-full"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              {t.reprocess.button}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
