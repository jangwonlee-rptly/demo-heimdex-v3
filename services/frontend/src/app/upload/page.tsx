'use client';

/**
 * Upload Page.
 *
 * Handles video file upload to Supabase Storage.
 * Provides drag-and-drop interface and upload progress tracking.
 * Initiates processing upon successful upload.
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';

export const dynamic = 'force-dynamic';

interface UploadProgress {
  stage: 'preparing' | 'uploading' | 'processing' | 'complete';
  percentage: number;
  message: string;
  bytesUploaded?: number;
  totalBytes?: number;
  speed?: number;
}

export default function UploadPage() {
  const { t } = useLanguage();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setUploadProgress(null);
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type.startsWith('video/')) {
        setFile(droppedFile);
        setError(null);
        setUploadProgress(null);
      } else {
        setError('Please drop a video file');
      }
    }
  }, []);

  const uploadWithProgress = async (
    storagePath: string,
    file: File,
    onProgress: (progress: number, bytesUploaded: number, speed: number) => void
  ): Promise<void> => {
    const startTime = Date.now();
    const totalSize = file.size;

    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const estimatedDuration = Math.max(2000, totalSize / (1024 * 500));
      const estimatedProgress = Math.min(95, (elapsed / estimatedDuration) * 100);
      const bytesUploaded = (estimatedProgress / 100) * totalSize;
      const speed = elapsed > 0 ? bytesUploaded / (elapsed / 1000) : 0;

      onProgress(estimatedProgress, bytesUploaded, speed);
    }, 100);

    try {
      const { error } = await supabase.storage
        .from('videos')
        .upload(storagePath, file, {
          cacheControl: '3600',
          upsert: false,
        });

      clearInterval(progressInterval);

      if (error) {
        console.error('Supabase upload error:', error);
        throw new Error(error.message || 'Upload failed');
      }

      const actualSpeed = totalSize / ((Date.now() - startTime) / 1000);
      onProgress(100, totalSize, actualSpeed);
    } catch (err: any) {
      clearInterval(progressInterval);
      console.error('Upload error:', err);
      throw err;
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      setUploadProgress({
        stage: 'preparing',
        percentage: 0,
        message: 'Preparing upload...',
      });

      const fileExtension = file.name.split('.').pop() || 'mp4';
      const filename = file.name;

      const uploadData = await apiRequest<{
        video_id: string;
        storage_path: string;
      }>(`/videos/upload-url?file_extension=${fileExtension}&filename=${encodeURIComponent(filename)}`, {
        method: 'POST',
      });

      setUploadProgress({
        stage: 'uploading',
        percentage: 0,
        message: 'Starting upload...',
        bytesUploaded: 0,
        totalBytes: file.size,
        speed: 0,
      });

      await uploadWithProgress(
        uploadData.storage_path,
        file,
        (percentage, bytesUploaded, speed) => {
          setUploadProgress({
            stage: 'uploading',
            percentage: Math.round(percentage),
            message: 'Uploading video...',
            bytesUploaded,
            totalBytes: file.size,
            speed,
          });
        }
      );

      setUploadProgress({
        stage: 'processing',
        percentage: 100,
        message: 'Finalizing upload...',
      });

      await apiRequest(`/videos/${uploadData.video_id}/uploaded`, {
        method: 'POST',
        body: JSON.stringify({}),
      });

      setUploadProgress({
        stage: 'complete',
        percentage: 100,
        message: 'Upload complete! Processing will begin shortly.',
      });

      setTimeout(() => {
        router.push('/dashboard');
      }, 2000);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.message);
      setUploadProgress(null);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] bg-accent-violet/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] bg-accent-cyan/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="card">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-cyan/20 to-accent-violet/20 mb-4">
              <svg className="w-8 h-8 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-surface-100 mb-2">{t.upload.title}</h1>
            <p className="text-surface-400">
              Upload a video to process and make it searchable
            </p>
          </div>

          <div className="space-y-6">
            {/* Drop Zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 ${
                isDragging
                  ? 'border-accent-cyan bg-accent-cyan/5'
                  : file
                  ? 'border-accent-cyan/50 bg-accent-cyan/5'
                  : 'border-surface-700 hover:border-surface-600'
              }`}
            >
              <input
                id="video-file"
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                disabled={uploading}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
              />

              {file ? (
                <div className="space-y-3">
                  <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-accent-cyan/10">
                    <svg className="w-7 h-7 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="23 7 16 12 23 17 23 7" />
                      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-surface-100">{file.name}</p>
                    <p className="text-sm text-surface-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      setFile(null);
                    }}
                    className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                  >
                    Choose different file
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-surface-700/50">
                    <svg className="w-7 h-7 text-surface-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-surface-200">
                      {isDragging ? 'Drop your video here' : 'Drag & drop your video here'}
                    </p>
                    <p className="text-sm text-surface-500 mt-1">
                      or click to browse
                    </p>
                  </div>
                  <p className="text-xs text-surface-600">
                    Supports MP4, MOV, AVI, MKV and more
                  </p>
                </div>
              )}
            </div>

            {/* Upload Progress */}
            {uploadProgress && (
              <div className="space-y-4 animate-fade-in">
                <div className="p-4 rounded-xl bg-surface-800/50 border border-surface-700/50">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      {uploadProgress.stage === 'complete' ? (
                        <div className="w-8 h-8 rounded-full bg-status-success/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-accent-cyan/20 flex items-center justify-center">
                          <div className="w-4 h-4 spinner" />
                        </div>
                      )}
                      <span className="text-sm font-medium text-surface-200">
                        {uploadProgress.message}
                      </span>
                    </div>
                    <span className="text-sm font-bold text-accent-cyan">
                      {uploadProgress.percentage}%
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${uploadProgress.percentage}%` }}
                    />
                  </div>

                  {/* Upload stats */}
                  {uploadProgress.stage === 'uploading' && uploadProgress.bytesUploaded !== undefined && uploadProgress.totalBytes && (
                    <div className="mt-3 flex items-center justify-between text-xs text-surface-500">
                      <span>
                        {(uploadProgress.bytesUploaded / 1024 / 1024).toFixed(1)} MB / {(uploadProgress.totalBytes / 1024 / 1024).toFixed(1)} MB
                      </span>
                      {uploadProgress.speed && uploadProgress.speed > 0 && (
                        <span>
                          {(uploadProgress.speed / 1024 / 1024).toFixed(2)} MB/s
                          {uploadProgress.bytesUploaded < uploadProgress.totalBytes && (
                            <span className="ml-2 text-surface-600">
                              {Math.ceil((uploadProgress.totalBytes - uploadProgress.bytesUploaded) / uploadProgress.speed)}s remaining
                            </span>
                          )}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="p-4 rounded-xl bg-status-error/10 border border-status-error/20 animate-fade-in">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-status-error flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="15" y1="9" x2="9" y2="15" />
                    <line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  <div>
                    <p className="font-medium text-status-error">{t.upload.uploadError}</p>
                    <p className="text-sm text-surface-400 mt-1">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn btn-primary w-full btn-lg"
            >
              {uploading ? (
                <>
                  <div className="w-5 h-5 spinner" />
                  {t.upload.uploading}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  {t.upload.uploadButton}
                </>
              )}
            </button>

            {/* Info */}
            <div className="p-4 rounded-xl bg-surface-800/30 border border-surface-700/30">
              <p className="text-sm font-medium text-surface-300 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                What happens next:
              </p>
              <ol className="space-y-2 text-sm text-surface-400">
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-surface-700 flex items-center justify-center text-xs font-medium text-surface-300 flex-shrink-0">1</span>
                  Your video will be uploaded to secure storage
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-surface-700 flex items-center justify-center text-xs font-medium text-surface-300 flex-shrink-0">2</span>
                  Scenes will be detected and analyzed by AI
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-surface-700 flex items-center justify-center text-xs font-medium text-surface-300 flex-shrink-0">3</span>
                  Transcripts and visual summaries will be generated
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-surface-700 flex items-center justify-center text-xs font-medium text-surface-300 flex-shrink-0">4</span>
                  Your video will become searchable!
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
