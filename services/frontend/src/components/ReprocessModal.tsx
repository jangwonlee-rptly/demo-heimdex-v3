'use client';

import { useState } from 'react';
import { useLanguage } from '@/lib/i18n';
import { apiRequest } from '@/lib/supabase';

interface ReprocessModalProps {
  videoId: string;
  videoName: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const SUPPORTED_LANGUAGES = [
  'ko', 'en', 'ja', 'zh', 'es', 'fr', 'de', 'ru', 'pt', 'it'
] as const;

type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export default function ReprocessModal({
  videoId,
  videoName,
  isOpen,
  onClose,
  onSuccess,
}: ReprocessModalProps) {
  const { t } = useLanguage();
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleReprocess = async () => {
    setIsProcessing(true);
    setError(null);

    try {
      await apiRequest(`/videos/${videoId}/reprocess`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transcript_language: selectedLanguage || null,
        }),
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to reprocess video:', err);
      setError(err.message || t.reprocess.error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && !isProcessing) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleBackdropClick}>
      <div className="modal-content">
        {/* Header */}
        <div className="px-6 py-5 border-b border-surface-700/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent-cyan/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-surface-100">
                {t.reprocess.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              disabled={isProcessing}
              className="text-surface-500 hover:text-surface-300 transition-colors disabled:opacity-50"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          <p className="text-sm text-surface-400 mb-5">
            {t.reprocess.description}
          </p>

          {/* Video name */}
          <div className="mb-5 p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
            <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-1">
              Video
            </p>
            <p className="text-surface-200 font-medium truncate">{videoName}</p>
          </div>

          {/* Language Selection */}
          <div className="mb-5">
            <label htmlFor="language-select" className="label">
              {t.reprocess.languageLabel}
            </label>
            <select
              id="language-select"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="select"
              disabled={isProcessing}
            >
              <option value="">{t.reprocess.autoDetect}</option>
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {t.reprocess.languages[lang as SupportedLanguage]}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-surface-500">
              {t.reprocess.languageHelp}
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-5 p-4 rounded-xl bg-status-error/10 border border-status-error/20">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-status-error flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <p className="text-sm text-status-error">{error}</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-700/50 bg-surface-800/30 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="btn btn-secondary"
          >
            {t.reprocess.cancel}
          </button>
          <button
            onClick={handleReprocess}
            disabled={isProcessing}
            className="btn btn-primary"
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 spinner" />
                {t.reprocess.processing}
              </>
            ) : (
              <>
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                {t.reprocess.confirm}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
