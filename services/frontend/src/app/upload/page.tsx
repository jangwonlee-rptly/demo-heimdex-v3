'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest, getAccessToken } from '@/lib/supabase';

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
   * Upload file to Supabase storage with progress tracking using XMLHttpRequest
   */
  const uploadWithProgress = (
    storagePath: string,
    file: File,
    onProgress: (progress: number, bytesUploaded: number, speed: number) => void
  ): Promise<void> => {
    return new Promise(async (resolve, reject) => {
      try {
        // Get Supabase storage URL and auth token
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
        const token = await getAccessToken();

        if (!supabaseUrl || !token) {
          throw new Error('Missing Supabase configuration');
        }

        const uploadUrl = `${supabaseUrl}/storage/v1/object/videos/${storagePath}`;

        const xhr = new XMLHttpRequest();

        // Track upload progress
        let startTime = Date.now();
        let lastLoaded = 0;
        let lastTime = startTime;

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percentage = (e.loaded / e.total) * 100;
            const currentTime = Date.now();
            const timeDiff = (currentTime - lastTime) / 1000; // seconds
            const bytesDiff = e.loaded - lastLoaded;
            const speed = timeDiff > 0 ? bytesDiff / timeDiff : 0;

            lastLoaded = e.loaded;
            lastTime = currentTime;

            onProgress(percentage, e.loaded, speed);
          }
        });

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Network error during upload'));
        });

        xhr.addEventListener('abort', () => {
          reject(new Error('Upload aborted'));
        });

        xhr.open('POST', uploadUrl);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.setRequestHeader('cache-control', '3600');
        xhr.setRequestHeader('content-type', file.type || 'application/octet-stream');

        xhr.send(file);
      } catch (err) {
        reject(err);
      }
    });
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
        <button
          onClick={() => router.push('/dashboard')}
          className="btn btn-secondary mb-6"
        >
          ← Back to Dashboard
        </button>

        <div className="card">
          <h1 className="text-2xl font-bold mb-2">Upload Video</h1>
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
                <p className="text-sm font-medium text-gray-700">Selected file:</p>
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
                <p className="font-medium">Upload failed</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn btn-primary w-full"
            >
              {uploading ? 'Uploading...' : 'Upload Video'}
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
