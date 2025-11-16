'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<string>('');
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
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setProgress('Preparing upload...');

    try {
      // Get file extension and name
      const fileExtension = file.name.split('.').pop() || 'mp4';
      const filename = file.name;

      // Create video record and get storage path
      setProgress('Creating video record...');
      const uploadData = await apiRequest<{
        video_id: string;
        storage_path: string;
      }>(`/videos/upload-url?file_extension=${fileExtension}&filename=${encodeURIComponent(filename)}`, {
        method: 'POST',
      });

      // Upload file directly to Supabase storage using client library
      setProgress(`Uploading video (${(file.size / 1024 / 1024).toFixed(1)} MB)...`);
      const { data: uploadResult, error: uploadError } = await supabase.storage
        .from('videos')
        .upload(uploadData.storage_path, file, {
          cacheControl: '3600',
          upsert: false,
        });

      if (uploadError) {
        throw new Error(`Upload failed: ${uploadError.message}`);
      }

      // Mark video as uploaded
      setProgress('Processing...');
      await apiRequest(`/videos/${uploadData.video_id}/uploaded`, {
        method: 'POST',
        body: JSON.stringify({}),
      });

      setProgress('Upload complete! Processing will begin shortly.');

      // Redirect to dashboard after a moment
      setTimeout(() => {
        router.push('/dashboard');
      }, 2000);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.message);
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

            {file && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm font-medium text-gray-700">Selected file:</p>
                <p className="text-sm text-gray-600">{file.name}</p>
                <p className="text-sm text-gray-600">
                  Size: {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            )}

            {progress && (
              <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded">
                {progress}
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
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
