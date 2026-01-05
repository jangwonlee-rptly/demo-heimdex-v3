/**
 * Video processing status enum.
 */
export type VideoStatus = 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED';

/**
 * User profile interface matching the database schema.
 */
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

/**
 * EXIF GPS metadata interface.
 */
export interface ExifGpsMetadata {
  latitude?: number;
  longitude?: number;
  altitude?: number;
  location_name?: string;
}

/**
 * EXIF camera metadata interface.
 */
export interface ExifCameraMetadata {
  make?: string;
  model?: string;
  software?: string;
}

/**
 * EXIF recording metadata interface.
 */
export interface ExifRecordingMetadata {
  iso?: number;
  focal_length?: number;
  aperture?: number;
  white_balance?: string;
}

/**
 * Full EXIF metadata interface.
 */
export interface ExifMetadata {
  gps?: ExifGpsMetadata;
  camera?: ExifCameraMetadata;
  recording?: ExifRecordingMetadata;
  other?: Record<string, unknown>;
}

/**
 * Video metadata interface.
 */
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
  video_summary?: string;
  has_rich_semantics?: boolean;
  error_message?: string;
  // EXIF metadata fields
  exif_metadata?: ExifMetadata;
  location_latitude?: number;
  location_longitude?: number;
  location_name?: string;
  camera_make?: string;
  camera_model?: string;
  created_at: string;
  updated_at: string;
}

/**
 * Embedding metadata for a scene.
 */
export interface EmbeddingMetadata {
  model: string;
  dimensions: number;
  input_text_hash: string;
  input_text_length: number;
}

/**
 * Processing statistics for a scene.
 */
export interface ProcessingStats {
  scene_duration_s: number;
  transcript_length: number;
  visual_analysis_called: boolean;
  visual_analysis_skipped_reason?: string;
  search_text_length: number;
  combined_text_length: number;
  keyframes_extracted: number;
  best_frame_found: boolean;
}

/**
 * Video scene interface representing a detected scene.
 */
export interface VideoScene {
  id: string;
  video_id: string;
  video_filename?: string; // Present only in search results
  index: number;
  start_s: number;
  end_s: number;
  transcript_segment?: string;
  visual_summary?: string;
  visual_description?: string;
  visual_entities?: string[];
  visual_actions?: string[];
  tags?: string[];
  combined_text?: string;
  thumbnail_url?: string;
  similarity?: number; // Present only in search results (DEPRECATED: use display_score or score)
  display_score?: number; // Calibrated score for UI display (0..1, capped at ~0.97)
  match_quality?: 'supported' | 'best_guess' | string; // Match quality hint for lookup queries
  created_at: string;
  // Sidecar v2 metadata fields
  sidecar_version?: string;
  search_text?: string;
  embedding_metadata?: EmbeddingMetadata;
  needs_reprocess?: boolean;
  processing_stats?: ProcessingStats;
}

/**
 * Search result interface from the search API.
 */
export interface SearchResult {
  query: string;
  results: VideoScene[];
  total: number;
  latency_ms: number;
  // Optional debug fields (only present if backend includes them)
  weight_source?: 'saved' | 'default' | 'request';
  fusion_weights?: {
    transcript: number;
    visual: number;
    summary: number;
    lexical: number;
  };
}

/**
 * Detailed video information including all scenes.
 */
export interface VideoDetails {
  video: Video;
  full_transcript?: string;
  scenes: VideoScene[];
  total_scenes: number;
  reprocess_hint?: string;
}

/**
 * Export status enum.
 */
export type ExportStatus = 'pending' | 'processing' | 'completed' | 'failed';

/**
 * Aspect ratio conversion strategy.
 */
export type AspectRatioStrategy = 'center_crop' | 'letterbox' | 'smart_crop';

/**
 * Export quality preset.
 */
export type OutputQuality = 'high' | 'medium';

/**
 * Scene export request.
 */
export interface CreateExportRequest {
  aspect_ratio_strategy?: AspectRatioStrategy;
  output_quality?: OutputQuality;
}

/**
 * Scene export response.
 */
export interface SceneExport {
  export_id: string;
  scene_id: string;
  status: ExportStatus;
  aspect_ratio_strategy: AspectRatioStrategy;
  output_quality: OutputQuality;
  download_url?: string;
  file_size_bytes?: number;
  duration_s?: number;
  resolution?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  expires_at: string;
}

/**
 * Person status enum (from backend: "active" or "archived").
 */
export type PersonStatus = 'active' | 'archived';

/**
 * Computed display status for UI purposes.
 */
export type PersonDisplayStatus = 'NEEDS_PHOTOS' | 'PROCESSING' | 'READY';

/**
 * Person photo state enum.
 */
export type PersonPhotoState = 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED';

/**
 * Person photo interface.
 */
export interface PersonPhoto {
  id: string;
  person_id: string;
  storage_path: string;
  state: PersonPhotoState;
  quality_score?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

/**
 * Person profile interface.
 */
export interface Person {
  id: string;
  display_name: string;
  status: PersonStatus;
  ready_photos_count: number;
  total_photos_count: number;
  has_query_embedding: boolean;
  photos?: PersonPhoto[];
  created_at: string;
  updated_at: string;
}

/**
 * Request to create a new person.
 */
export interface CreatePersonRequest {
  display_name: string;
}

/**
 * Response when requesting a photo upload URL.
 */
export interface PersonPhotoUploadUrl {
  upload_url: string;
  storage_path: string;
  photo_id: string;
}
