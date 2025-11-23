'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest, getAccessToken } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

export const dynamic = 'force-dynamic';

interface UploadProgress {
  stage: 'preparing' | 'uploading' | 'processing' | 'complete';
  percentage: number;
  message: string;
  bytesUploaded?: number;
  totalBytes?: number;
  speed?: number; // bytes per second
}

export default function UploadPage() {
  const { t } = useLanguage();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  /**
   * Upload file to Supabase storage with progress tracking
   * Uses Supabase client library for better reliability and automatic auth handling
   */
  const uploadWithProgress = async (
    storagePath: string,
    file: File,
    onProgress: (progress: number, bytesUploaded: number, speed: number) => void
  ): Promise<void> => {
    const startTime = Date.now();
    const totalSize = file.size;

    // Simulate progress updates since Supabase JS client doesn't expose native progress yet
    // We'll show gradual progress and complete when upload finishes
    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      // Estimate progress based on file size and elapsed time
      // Assume minimum 2 seconds, scale with file size (slower for larger files)
      const estimatedDuration = Math.max(2000, totalSize / (1024 * 500)); // ~500KB/s estimate
      const estimatedProgress = Math.min(95, (elapsed / estimatedDuration) * 100);
      const bytesUploaded = (estimatedProgress / 100) * totalSize;
      const speed = elapsed > 0 ? bytesUploaded / (elapsed / 1000) : 0;

      onProgress(estimatedProgress, bytesUploaded, speed);
    }, 100);

    try {
      // Upload using Supabase client - handles auth, CORS, and policies automatically
      const { data, error } = await supabase.storage
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

      // Complete at 100%
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
      // Stage 1: Preparing
      setUploadProgress({
        stage: 'preparing',
        percentage: 0,
        message: 'Preparing upload...',
      });

      // Get file extension and name
      const fileExtension = file.name.split('.').pop() || 'mp4';
      const filename = file.name;

      // Create video record and get storage path
      const uploadData = await apiRequest<{
        video_id: string;
        storage_path: string;
      }>(`/videos/upload-url?file_extension=${fileExtension}&filename=${encodeURIComponent(filename)}`, {
        method: 'POST',
      });

      // Stage 2: Uploading
      setUploadProgress({
        stage: 'uploading',
        percentage: 0,
        message: 'Starting upload...',
        bytesUploaded: 0,
        totalBytes: file.size,
        speed: 0,
      });

      // Upload file with progress tracking
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

      // Stage 3: Processing
      setUploadProgress({
        stage: 'processing',
        percentage: 100,
        message: 'Finalizing upload...',
      });

      // Mark video as uploaded
      await apiRequest(`/videos/${uploadData.video_id}/uploaded`, {
        method: 'POST',
        body: JSON.stringify({}),
      });

      // Stage 4: Complete
      setUploadProgress({
        stage: 'complete',
        percentage: 100,
        message: 'Upload complete! Processing will begin shortly.',
      });

      // Redirect to dashboard after a moment
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
    <div className="min-h-screen p-6">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => router.push('/dashboard')}
            className="btn btn-secondary"
          >
            ← {t.upload.backToDashboard}
          </button>
          <LanguageToggle />
        </div>

        <div className="card">
          <h1 className="text-2xl font-bold mb-2">{t.upload.title}</h1>
          <p className="text-gray-600 mb-6">
            Upload a video to process and make it searchable
          </p>

          <div className="space-y-6">
            <div>
              <label
                htmlFor="video-file"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Select Video File
              </label>
              <input
                id="video-file"
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                disabled={uploading}
                className="block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-semibold
                  file:bg-primary-50 file:text-primary-700
                  hover:file:bg-primary-100
                  disabled:opacity-50"
              />
            </div>

            {file && !uploading && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm font-medium text-gray-700">{t.upload.selectedFile}:</p>
                <p className="text-sm text-gray-600">{file.name}</p>
                <p className="text-sm text-gray-600">
                  Size: {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            )}

            {uploadProgress && (
              <div className="space-y-3">
                <div className="bg-blue-50 border border-blue-200 px-4 py-3 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-blue-900">
                      {uploadProgress.message}
                    </span>
                    <span className="text-sm font-semibold text-blue-900">
                      {uploadProgress.percentage}%
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-blue-100 rounded-full h-3 overflow-hidden">
                    <div
                      className="bg-blue-600 h-full transition-all duration-300 ease-out rounded-full"
                      style={{ width: `${uploadProgress.percentage}%` }}
                    >
                      <div className="h-full w-full bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-shimmer" />
                    </div>
                  </div>

                  {/* Upload stats */}
                  {uploadProgress.stage === 'uploading' && uploadProgress.bytesUploaded !== undefined && uploadProgress.totalBytes && (
                    <div className="mt-3 flex items-center justify-between text-xs text-blue-700">
                      <span>
                        {(uploadProgress.bytesUploaded / 1024 / 1024).toFixed(1)} MB / {(uploadProgress.totalBytes / 1024 / 1024).toFixed(1)} MB
                      </span>
                      {uploadProgress.speed && uploadProgress.speed > 0 && (
                        <span>
                          {(uploadProgress.speed / 1024 / 1024).toFixed(2)} MB/s
                          {uploadProgress.bytesUploaded < uploadProgress.totalBytes && (
                            <span className="ml-2">
                              • {Math.ceil((uploadProgress.totalBytes - uploadProgress.bytesUploaded) / uploadProgress.speed)}s remaining
                            </span>
                          )}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                <p className="font-medium">{t.upload.uploadError}</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn btn-primary w-full"
            >
              {uploading ? t.upload.uploading : t.upload.uploadButton}
            </button>

            <div className="text-sm text-gray-600">
              <p className="font-medium mb-2">What happens next:</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Your video will be uploaded to secure storage</li>
                <li>It will be queued for processing</li>
                <li>Scenes will be detected and analyzed</li>
                <li>Transcripts and visual summaries will be generated</li>
                <li>Your video will become searchable!</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
