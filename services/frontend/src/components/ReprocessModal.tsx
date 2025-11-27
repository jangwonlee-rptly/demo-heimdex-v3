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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            {t.reprocess.title}
          </h2>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          <p className="text-sm text-gray-600 mb-4">
            {t.reprocess.description}
          </p>

          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-1">
              Video: <span className="font-normal">{videoName}</span>
            </p>
          </div>

          {/* Language Selection */}
          <div className="mb-4">
            <label
              htmlFor="language-select"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t.reprocess.languageLabel}
            </label>
            <select
              id="language-select"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={isProcessing}
            >
              <option value="">{t.reprocess.autoDetect}</option>
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {t.reprocess.languages[lang as SupportedLanguage]}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {t.reprocess.languageHelp}
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3">
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
              <span className="flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                {t.reprocess.processing}
              </span>
            ) : (
              t.reprocess.confirm
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
