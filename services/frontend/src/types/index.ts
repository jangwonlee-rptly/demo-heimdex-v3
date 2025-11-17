export type VideoStatus = 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED';

export interface UserProfile {
  user_id: string;
  full_name: string;
  industry?: string;
  job_title?: string;
  preferred_language: string;
  marketing_consent: boolean;
  marketing_consent_at?: string;
  created_at: string;
  updated_at: string;
}

export interface Video {
  id: string;
  owner_id: string;
  storage_path: string;
  status: VideoStatus;
  filename?: string;
  duration_s?: number;
  frame_rate?: number;
  width?: number;
  height?: number;
  video_created_at?: string;
  thumbnail_url?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface VideoScene {
  id: string;
  video_id: string;
  index: number;
  start_s: number;
  end_s: number;
  transcript_segment?: string;
  visual_summary?: string;
  combined_text?: string;
  thumbnail_url?: string;
  similarity?: number;
  created_at: string;
}

export interface SearchResult {
  query: string;
  results: VideoScene[];
  total: number;
  latency_ms: number;
}
