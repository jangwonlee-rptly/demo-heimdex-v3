'use client';

import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import type { VideoScene, CreateExportRequest, SceneExport, AspectRatioStrategy, OutputQuality } from '@/types';

interface ExportShortModalProps {
  scene: VideoScene;
  isOpen: boolean;
  onClose: () => void;
}

const MAX_SHORTS_DURATION = 180; // YouTube Shorts max duration in seconds
const POLL_INTERVAL = 2000; // Poll every 2 seconds

export default function ExportShortModal({ scene, isOpen, onClose }: ExportShortModalProps) {
  const { t } = useLanguage();
  const [aspectRatioStrategy, setAspectRatioStrategy] = useState<AspectRatioStrategy>('center_crop');
  const [outputQuality, setOutputQuality] = useState<OutputQuality>('high');
  const [isExporting, setIsExporting] = useState(false);
  const [exportData, setExportData] = useState<SceneExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitError, setRateLimitError] = useState<string | null>(null);

  const sceneDuration = scene.end_s - scene.start_s;
  const isTooLong = sceneDuration > MAX_SHORTS_DURATION;

  // Poll for export status
  useEffect(() => {
    if (!exportData || exportData.status === 'completed' || exportData.status === 'failed') {
      return;
    }

    const pollStatus = async () => {
      try {
        const updated = await apiRequest<SceneExport>(`/exports/${exportData.export_id}`);
        setExportData(updated);

        if (updated.status === 'failed') {
          setError(updated.error_message || 'Export failed');
          setIsExporting(false);
        } else if (updated.status === 'completed') {
          setIsExporting(false);
        }
      } catch (err: any) {
        console.error('Failed to poll export status:', err);
        setError(err.message || 'Failed to check export status');
        setIsExporting(false);
      }
    };

    const interval = setInterval(pollStatus, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [exportData]);

  // Calculate expiration info
  const getExpirationInfo = (expiresAt: string) => {
    const expires = new Date(expiresAt);
    const now = new Date();
    const hoursRemaining = Math.floor((expires.getTime() - now.getTime()) / (1000 * 60 * 60));

    if (hoursRemaining < 0) {
      return { expired: true, message: 'Expired' };
    }

    if (hoursRemaining < 1) {
      const minutesRemaining = Math.floor((expires.getTime() - now.getTime()) / (1000 * 60));
      return { expired: false, message: `Expires in ${minutesRemaining} min` };
    }

    return { expired: false, message: `Expires in ${hoursRemaining}h` };
  };

  const handleExport = async () => {
    setError(null);
    setRateLimitError(null);
    setIsExporting(true);

    try {
      const request: CreateExportRequest = {
        aspect_ratio_strategy: aspectRatioStrategy,
        output_quality: outputQuality,
      };

      const result = await apiRequest<SceneExport>(`/scenes/${scene.id}/export-short`, {
        method: 'POST',
        body: JSON.stringify(request),
      });

      setExportData(result);
    } catch (err: any) {
      console.error('Export failed:', err);

      // Check if rate limit error
      if (err.message.includes('Daily export limit') || err.message.includes('limit reached')) {
        setRateLimitError(err.message);
      } else {
        setError(err.message || 'Failed to create export');
      }
      setIsExporting(false);
    }
  };

  const handleDownload = () => {
    if (exportData?.download_url) {
      window.open(exportData.download_url, '_blank');
    }
  };

  const handleClose = () => {
    setExportData(null);
    setError(null);
    setRateLimitError(null);
    setIsExporting(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md mx-4 bg-surface-800 rounded-2xl shadow-2xl border border-surface-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-surface-700">
          <h2 className="text-xl font-bold text-surface-100">{t.export.title}</h2>
          <button
            onClick={handleClose}
            className="text-surface-400 hover:text-surface-200 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Scene Info */}
          <div className="bg-surface-900 rounded-lg p-4">
            <div className="text-sm text-surface-400">{t.export.sceneDuration}</div>
            <div className="text-2xl font-bold text-surface-100">
              {sceneDuration.toFixed(1)}s
            </div>
            {isTooLong && (
              <div className="mt-2 text-sm text-status-error">
                ⚠️ {t.export.exceedsMax}
              </div>
            )}
          </div>

          {/* Export Form (only show if not exporting) */}
          {!exportData && !rateLimitError && (
            <>
              {/* Aspect Ratio Strategy */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">
                  {t.export.aspectRatioStrategy}
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setAspectRatioStrategy('center_crop')}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      aspectRatioStrategy === 'center_crop'
                        ? 'border-accent-cyan bg-accent-cyan/10'
                        : 'border-surface-700 hover:border-surface-600'
                    }`}
                  >
                    <div className="font-medium text-surface-100">{t.export.centerCrop}</div>
                    <div className="text-xs text-surface-400 mt-1">{t.export.cropTo916}</div>
                  </button>
                  <button
                    onClick={() => setAspectRatioStrategy('letterbox')}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      aspectRatioStrategy === 'letterbox'
                        ? 'border-accent-cyan bg-accent-cyan/10'
                        : 'border-surface-700 hover:border-surface-600'
                    }`}
                  >
                    <div className="font-medium text-surface-100">{t.export.letterbox}</div>
                    <div className="text-xs text-surface-400 mt-1">{t.export.addBlackBars}</div>
                  </button>
                </div>
              </div>

              {/* Quality Preset */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">
                  {t.export.quality}
                </label>
                <select
                  value={outputQuality}
                  onChange={(e) => setOutputQuality(e.target.value as OutputQuality)}
                  className="w-full px-4 py-2 bg-surface-900 border border-surface-700 rounded-lg text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-cyan"
                >
                  <option value="high">{t.export.highQuality}</option>
                  <option value="medium">{t.export.mediumQuality}</option>
                </select>
              </div>
            </>
          )}

          {/* Export Status */}
          {exportData && (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-surface-400">{t.export.status}</span>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    exportData.status === 'completed'
                      ? 'bg-status-success/20 text-status-success'
                      : exportData.status === 'failed'
                      ? 'bg-status-error/20 text-status-error'
                      : 'bg-accent-cyan/20 text-accent-cyan'
                  }`}
                >
                  {exportData.status === 'pending' && t.export.queued}
                  {exportData.status === 'processing' && t.export.processing}
                  {exportData.status === 'completed' && t.export.ready}
                  {exportData.status === 'failed' && t.export.failed}
                </span>
              </div>

              {/* Processing Indicator */}
              {(exportData.status === 'pending' || exportData.status === 'processing') && (
                <div className="bg-surface-900 rounded-lg p-4">
                  <div className="flex items-center gap-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-accent-cyan border-t-transparent"></div>
                    <div className="text-sm text-surface-300">
                      {exportData.status === 'pending' ? t.export.waitingForWorker : t.export.convertingVideo}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-surface-500">{t.export.usuallyTakes}</div>
                </div>
              )}

              {/* Completed: Download Button */}
              {exportData.status === 'completed' && exportData.download_url && (
                <div className="space-y-3">
                  <button
                    onClick={handleDownload}
                    className="w-full btn btn-primary flex items-center justify-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t.export.downloadVideo}
                  </button>

                  {/* File Info */}
                  <div className="bg-surface-900 rounded-lg p-3 text-sm space-y-1">
                    {exportData.file_size_bytes && (
                      <div className="flex justify-between">
                        <span className="text-surface-400">{t.export.size}:</span>
                        <span className="text-surface-200">{(exportData.file_size_bytes / 1024 / 1024).toFixed(1)} MB</span>
                      </div>
                    )}
                    {exportData.resolution && (
                      <div className="flex justify-between">
                        <span className="text-surface-400">{t.export.resolution}:</span>
                        <span className="text-surface-200">{exportData.resolution}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-surface-400">{t.export.expires}:</span>
                      <span className="text-status-warning">{getExpirationInfo(exportData.expires_at).message}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Failed: Error Message */}
              {exportData.status === 'failed' && (
                <div className="bg-status-error/10 border border-status-error/20 rounded-lg p-4">
                  <div className="text-sm font-medium text-status-error mb-1">{t.export.exportFailed}</div>
                  <div className="text-sm text-surface-400">{exportData.error_message || t.export.unknownError}</div>
                </div>
              )}
            </div>
          )}

          {/* Rate Limit Error */}
          {rateLimitError && (
            <div className="bg-status-warning/10 border border-status-warning/20 rounded-lg p-4">
              <div className="text-sm font-medium text-status-warning mb-1">{t.export.limitReached}</div>
              <div className="text-sm text-surface-400">{rateLimitError}</div>
            </div>
          )}

          {/* General Error */}
          {error && !exportData && (
            <div className="bg-status-error/10 border border-status-error/20 rounded-lg p-4">
              <div className="text-sm text-status-error">{error}</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-surface-700">
          {!exportData && !rateLimitError ? (
            <>
              <button onClick={handleClose} className="flex-1 btn btn-ghost">
                {t.export.cancel}
              </button>
              <button
                onClick={handleExport}
                disabled={isExporting || isTooLong}
                className="flex-1 btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isExporting ? t.export.starting : t.export.exportButton}
              </button>
            </>
          ) : (
            <button onClick={handleClose} className="flex-1 btn btn-primary">
              {t.export.close}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
