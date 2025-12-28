'use client';

import { useEffect, useRef } from 'react';
import { useLanguage } from '@/lib/i18n';

interface JobProgress {
  stage?: string;
  done: number;
  total: number;
}

interface JobOutput {
  mp4_url?: string;
  storage_path?: string;
  file_size_bytes?: number;
  duration_s?: number;
}

interface JobError {
  message: string;
  detail?: string;
}

export interface HighlightJob {
  job_id: string;
  status: 'queued' | 'processing' | 'done' | 'error';
  progress?: JobProgress;
  output?: JobOutput;
  error?: JobError;
  created_at: string;
  updated_at: string;
}

interface HighlightJobStatusProps {
  job: HighlightJob | null;
  onPoll: () => void;
  onDismiss: () => void;
  onRetry?: () => void;
  className?: string;
}

/**
 * HighlightJobStatus component displays the current status of a highlight export job.
 * Polls the backend when job is in progress.
 */
export function HighlightJobStatus({
  job,
  onPoll,
  onDismiss,
  onRetry,
  className = '',
}: HighlightJobStatusProps) {
  const { t } = useLanguage();
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Poll for job status updates
  useEffect(() => {
    if (!job) return;

    const shouldPoll = job.status === 'queued' || job.status === 'processing';

    if (shouldPoll) {
      // Clear any existing interval
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }

      // Start polling every 2 seconds
      pollIntervalRef.current = setInterval(() => {
        onPoll();
      }, 2000);
    } else {
      // Clear interval when job is done or errored
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [job?.status, onPoll]);

  if (!job) return null;

  const getStageLabel = (stage?: string): string => {
    switch (stage) {
      case 'cutting':
        return t.highlightReel?.cuttingScenes || 'Cutting scenes';
      case 'concat':
        return t.highlightReel?.concatenating || 'Concatenating';
      case 'upload':
        return t.highlightReel?.uploading || 'Uploading';
      case 'complete':
        return t.highlightReel?.complete || 'Complete';
      default:
        return t.highlightReel?.processing || 'Processing';
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'queued':
        return 'text-surface-400';
      case 'processing':
        return 'text-accent-cyan';
      case 'done':
        return 'text-status-success';
      case 'error':
        return 'text-status-error';
      default:
        return 'text-surface-400';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className={`card ${className}`}>
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className={`flex-shrink-0 ${getStatusColor(job.status)}`}>
          {job.status === 'queued' && (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          )}
          {job.status === 'processing' && (
            <div className="w-5 h-5 spinner" />
          )}
          {job.status === 'done' && (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
          )}
          {job.status === 'error' && (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-sm font-medium text-surface-100">
              {t.highlightReel?.jobStatus || 'Export Status'}
            </h4>
            <span className={`text-xs font-medium ${getStatusColor(job.status)}`}>
              {job.status === 'queued' && (t.highlightReel?.queued || 'Queued')}
              {job.status === 'processing' && (t.highlightReel?.processing || 'Processing')}
              {job.status === 'done' && (t.highlightReel?.complete || 'Complete')}
              {job.status === 'error' && (t.highlightReel?.failed || 'Failed')}
            </span>
          </div>

          {/* Progress bar for processing */}
          {job.status === 'processing' && job.progress && (
            <div className="mb-2">
              <div className="flex items-center justify-between text-xs text-surface-400 mb-1">
                <span>{getStageLabel(job.progress.stage)}</span>
                <span>
                  {job.progress.done} {t.highlightReel?.progressOf || 'of'} {job.progress.total}
                </span>
              </div>
              <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-cyan rounded-full transition-all duration-300"
                  style={{
                    width: job.progress.total > 0
                      ? `${(job.progress.done / job.progress.total) * 100}%`
                      : '0%',
                  }}
                />
              </div>
            </div>
          )}

          {/* Queued message */}
          {job.status === 'queued' && (
            <p className="text-xs text-surface-500">
              Waiting for worker to start processing...
            </p>
          )}

          {/* Success state with download */}
          {job.status === 'done' && job.output?.mp4_url && (
            <div className="space-y-2">
              <p className="text-xs text-surface-400">
                {t.highlightReel?.downloadReady || 'Your highlight reel is ready!'}
                {job.output.file_size_bytes && (
                  <span className="ml-2 text-surface-500">
                    ({formatFileSize(job.output.file_size_bytes)})
                  </span>
                )}
              </p>
              <div className="flex items-center gap-2">
                <a
                  href={job.output.mp4_url}
                  download
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition-all flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  {t.highlightReel?.downloadButton || 'Download'}
                </a>
                <button
                  onClick={onDismiss}
                  className="px-2 py-1 text-xs text-surface-500 hover:text-surface-300"
                >
                  {t.highlightReel?.dismiss || 'Dismiss'}
                </button>
              </div>
            </div>
          )}

          {/* Error state */}
          {job.status === 'error' && job.error && (
            <div className="space-y-2">
              <p className="text-xs text-status-error">
                {job.error.message}
              </p>
              <div className="flex items-center gap-2">
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-800/50 border border-surface-700/30 text-surface-300 hover:bg-surface-700/50 transition-all"
                  >
                    {t.highlightReel?.retry || 'Retry'}
                  </button>
                )}
                <button
                  onClick={onDismiss}
                  className="px-2 py-1 text-xs text-surface-500 hover:text-surface-300"
                >
                  {t.highlightReel?.dismiss || 'Dismiss'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Close button for queued/processing states */}
        {(job.status === 'queued' || job.status === 'processing') && (
          <button
            onClick={onDismiss}
            className="flex-shrink-0 p-1 text-surface-500 hover:text-surface-300 transition-colors"
            title={t.highlightReel?.dismiss || 'Dismiss'}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
