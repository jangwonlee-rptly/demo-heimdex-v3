/**
 * People API client module.
 * Provides type-safe wrappers for person management endpoints.
 */

import { apiRequest } from './supabase';
import type {
  Person,
  PersonDisplayStatus,
  CreatePersonRequest,
  PersonPhotoUploadUrl,
} from '@/types';

/**
 * Compute display status from person data.
 * Backend returns "active" or "archived", but UI needs semantic status.
 */
export function getPersonDisplayStatus(person: Person): PersonDisplayStatus {
  if (person.total_photos_count === 0) {
    return 'NEEDS_PHOTOS';
  }
  if (person.has_query_embedding && person.ready_photos_count > 0) {
    return 'READY';
  }
  return 'PROCESSING';
}

/**
 * List all persons for the current user.
 */
export async function listPersons(): Promise<Person[]> {
  const response = await apiRequest<{ persons: Person[] }>('/persons', {
    method: 'GET',
  });
  return response.persons;
}

/**
 * Create a new person profile.
 */
export async function createPerson(displayName: string): Promise<Person> {
  const body: CreatePersonRequest = { display_name: displayName };
  return apiRequest<Person>('/persons', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Get detailed information about a specific person.
 */
export async function getPerson(personId: string): Promise<Person> {
  const response = await apiRequest<{
    person: Omit<Person, 'photos'>;
    photos: Person['photos'];
  }>(`/persons/${personId}`, {
    method: 'GET',
  });
  return {
    ...response.person,
    photos: response.photos,
  };
}

/**
 * Get a signed upload URL for uploading a person photo.
 */
export async function getPersonPhotoUploadUrl(
  personId: string
): Promise<PersonPhotoUploadUrl> {
  return apiRequest<PersonPhotoUploadUrl>(
    `/persons/${personId}/photos/upload-url`,
    {
      method: 'POST',
    }
  );
}

/**
 * Mark a photo upload as complete after uploading to storage.
 */
export async function completePersonPhotoUpload(
  personId: string,
  photoId: string,
  storagePath: string
): Promise<void> {
  // Backend expects storage_path as a query parameter, not in the body
  const url = `/persons/${personId}/photos/${photoId}/complete?storage_path=${encodeURIComponent(storagePath)}`;
  await apiRequest<void>(url, {
    method: 'POST',
  });
}

/**
 * Delete a person and all associated photos.
 */
export async function deletePerson(personId: string): Promise<void> {
  await apiRequest<void>(`/persons/${personId}`, {
    method: 'DELETE',
  });
}

/**
 * Upload a photo file directly to the signed URL.
 * This bypasses the apiRequest wrapper since we're uploading directly to storage.
 */
export async function uploadPhotoToStorage(
  uploadUrl: string,
  file: File
): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type,
    },
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
}
