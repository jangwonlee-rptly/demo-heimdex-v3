'use client';

/**
 * People Management Page.
 *
 * Allows users to create and manage person profiles for face-based search.
 * Provides photo upload and status tracking capabilities.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import {
  listPersons,
  createPerson,
  getPerson,
  deletePerson,
  getPersonPhotoUploadUrl,
  uploadPhotoToStorage,
  completePersonPhotoUpload,
  getPersonDisplayStatus,
} from '@/lib/people-api';
import type { Person, PersonPhoto } from '@/types';
import { useLanguage } from '@/lib/i18n';

export const dynamic = 'force-dynamic';

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [notification, setNotification] = useState<{
    message: string;
    type: 'success' | 'info' | 'error';
  } | null>(null);
  const router = useRouter();
  const { t } = useLanguage();

  // Load people list
  const loadPeople = useCallback(async () => {
    try {
      const data = await listPersons();
      setPeople(data);
    } catch (error) {
      console.error('Failed to load people:', error);
      showNotification(t.common.error, 'error');
    }
  }, [t]);

  useEffect(() => {
    const init = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      await loadPeople();
      setLoading(false);
    };

    init();
  }, [router, loadPeople]);

  const showNotification = (message: string, type: 'success' | 'info' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleCreatePerson = async (displayName: string) => {
    try {
      const newPerson = await createPerson(displayName);
      setPeople([...people, newPerson]);
      setShowCreateModal(false);
      showNotification(t.people.created, 'success');
    } catch (error) {
      console.error('Failed to create person:', error);
      showNotification(t.common.error, 'error');
    }
  };

  const handleDeletePerson = async (personId: string) => {
    if (!confirm(t.people.deleteConfirm)) return;

    try {
      await deletePerson(personId);
      setPeople(people.filter((p) => p.id !== personId));
      if (selectedPerson?.id === personId) {
        setSelectedPerson(null);
      }
      showNotification(t.people.deleted, 'success');
    } catch (error) {
      console.error('Failed to delete person:', error);
      showNotification(t.people.deleteError, 'error');
    }
  };

  const handleViewDetails = async (personId: string) => {
    try {
      const person = await getPerson(personId);
      setSelectedPerson(person);
    } catch (error) {
      console.error('Failed to load person details:', error);
      showNotification(t.common.error, 'error');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-surface-300">{t.common.loading}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-accent-cyan/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 left-1/4 w-[500px] h-[500px] bg-accent-violet/5 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-surface-50 mb-2">{t.people.title}</h1>
          <p className="text-surface-300">{t.people.subtitle}</p>
        </div>

        {/* Notification */}
        {notification && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              notification.type === 'success'
                ? 'bg-green-500/10 text-green-400'
                : notification.type === 'error'
                ? 'bg-red-500/10 text-red-400'
                : 'bg-blue-500/10 text-blue-400'
            }`}
          >
            {notification.message}
          </div>
        )}

        {/* Action Bar */}
        <div className="mb-6">
          <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            {t.people.addPerson}
          </button>
        </div>

        {/* People Grid */}
        {people.length === 0 ? (
          <div className="card p-12 text-center">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-surface-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
            <p className="text-surface-300 text-lg mb-2">{t.people.noPeople}</p>
            <p className="text-surface-400 text-sm">{t.people.addFirstPerson}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {people.map((person) => (
              <PersonCard
                key={person.id}
                person={person}
                onViewDetails={() => handleViewDetails(person.id)}
                onDelete={() => handleDeletePerson(person.id)}
                t={t}
              />
            ))}
          </div>
        )}

        {/* Create Person Modal */}
        {showCreateModal && (
          <CreatePersonModal
            onClose={() => setShowCreateModal(false)}
            onCreate={handleCreatePerson}
            t={t}
          />
        )}

        {/* Person Details Modal */}
        {selectedPerson && (
          <PersonDetailsModal
            person={selectedPerson}
            onClose={() => setSelectedPerson(null)}
            onUpdate={loadPeople}
            t={t}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Person Card Component
 */
function PersonCard({
  person,
  onViewDetails,
  onDelete,
  t,
}: {
  person: Person;
  onViewDetails: () => void;
  onDelete: () => void;
  t: any;
}) {
  const displayStatus = getPersonDisplayStatus(person);
  const statusConfig = {
    READY: { label: t.people.status.READY, color: 'bg-green-500/10 text-green-400' },
    PROCESSING: {
      label: t.people.status.PROCESSING,
      color: 'bg-yellow-500/10 text-yellow-400',
    },
    NEEDS_PHOTOS: { label: t.people.status.NEEDS_PHOTOS, color: 'bg-red-500/10 text-red-400' },
  };

  const status = statusConfig[displayStatus];

  return (
    <div className="card p-6 hover:border-accent-cyan/30 transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-surface-50 mb-2">{person.display_name}</h3>
          <span className={`status-badge ${status.color} text-xs`}>{status.label}</span>
        </div>
      </div>

      <div className="space-y-2 mb-4 text-sm">
        <div className="text-surface-300">
          {t.people.photos}: {person.ready_photos_count} {t.people.readyPhotos} /{' '}
          {person.total_photos_count} {t.people.totalPhotos}
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={onViewDetails} className="btn btn-secondary flex-1 text-sm">
          {t.people.viewDetails}
        </button>
        <button
          onClick={onDelete}
          className="btn btn-ghost text-red-400 hover:bg-red-500/10 text-sm"
        >
          {t.common.delete}
        </button>
      </div>
    </div>
  );
}

/**
 * Create Person Modal
 */
function CreatePersonModal({
  onClose,
  onCreate,
  t,
}: {
  onClose: () => void;
  onCreate: (displayName: string) => Promise<void>;
  t: any;
}) {
  const [displayName, setDisplayName] = useState('');
  const [creating, setCreating] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim()) return;

    setCreating(true);
    try {
      await onCreate(displayName.trim());
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="card p-6 max-w-md w-full">
        <h2 className="text-2xl font-bold text-surface-50 mb-4">{t.people.addPerson}</h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-surface-200 text-sm font-medium mb-2">
              {t.people.personName}
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t.people.personNamePlaceholder}
              className="input w-full"
              required
              autoFocus
            />
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={creating || !displayName.trim()}
              className="btn btn-primary flex-1"
            >
              {creating ? t.people.creating : t.people.createPerson}
            </button>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              {t.common.cancel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Person Details Modal with Photo Management
 */
function PersonDetailsModal({
  person: initialPerson,
  onClose,
  onUpdate,
  t,
}: {
  person: Person;
  onClose: () => void;
  onUpdate: () => Promise<void>;
  t: any;
}) {
  const [person, setPerson] = useState(initialPerson);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // State for instant preview during upload
  const [uploadingPreviews, setUploadingPreviews] = useState<Record<string, string>>({});

  // State for signed URLs (cached)
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});

  // Poll for person updates when there are processing photos
  useEffect(() => {
    const hasProcessingPhotos =
      person.photos?.some((p) => p.state === 'PROCESSING' || p.state === 'UPLOADED') || false;

    if (hasProcessingPhotos) {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const updated = await getPerson(person.id);
          setPerson(updated);
        } catch (error) {
          console.error('Failed to poll person status:', error);
        }
      }, 3000);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [person]);

  // Generate signed URLs for persisted photos
  useEffect(() => {
    const generateSignedUrls = async () => {
      if (!person.photos) return;

      const newUrls: Record<string, string> = {};

      for (const photo of person.photos) {
        // Skip if we already have a URL
        if (signedUrls[photo.id]) continue;

        try {
          // Generate signed URL (valid for 1 hour)
          const { data, error } = await supabase.storage
            .from('videos')
            .createSignedUrl(photo.storage_path, 3600);

          if (error) throw error;
          if (data?.signedUrl) {
            newUrls[photo.id] = data.signedUrl;
          }
        } catch (error) {
          console.error(`Failed to generate signed URL for photo ${photo.id}:`, error);
        }
      }

      if (Object.keys(newUrls).length > 0) {
        setSignedUrls((prev) => ({ ...prev, ...newUrls }));
      }
    };

    generateSignedUrls();
  }, [person.photos]);

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      Object.values(uploadingPreviews).forEach((url) => {
        URL.revokeObjectURL(url);
      });
    };
  }, [uploadingPreviews]);

  const handlePhotoUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setUploading(true);

    // Create instant previews for all files
    const previews: Record<string, string> = {};
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const tempId = `temp-${Date.now()}-${i}`;
      previews[tempId] = URL.createObjectURL(file);
    }
    setUploadingPreviews(previews);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const tempId = `temp-${Date.now()}-${i}`;

        // Get upload URL
        const { upload_url, storage_path, photo_id } = await getPersonPhotoUploadUrl(person.id);

        // Upload to storage
        await uploadPhotoToStorage(upload_url, file);

        // Mark as complete
        await completePersonPhotoUpload(person.id, photo_id, storage_path);

        // Remove temp preview
        if (previews[tempId]) {
          URL.revokeObjectURL(previews[tempId]);
          setUploadingPreviews((prev) => {
            const updated = { ...prev };
            delete updated[tempId];
            return updated;
          });
        }
      }

      // Refresh person details
      const updated = await getPerson(person.id);
      setPerson(updated);
      await onUpdate();
    } catch (error) {
      console.error('Failed to upload photos:', error);
      alert(t.people.photoUploadError);
    } finally {
      setUploading(false);
      setUploadingPreviews({});
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const photoStateConfig = {
    UPLOADED: { label: t.people.photoState.UPLOADED, color: 'bg-blue-500/10 text-blue-400' },
    PROCESSING: {
      label: t.people.photoState.PROCESSING,
      color: 'bg-yellow-500/10 text-yellow-400',
    },
    READY: { label: t.people.photoState.READY, color: 'bg-green-500/10 text-green-400' },
    FAILED: { label: t.people.photoState.FAILED, color: 'bg-red-500/10 text-red-400' },
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="card p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-surface-50 mb-2">{person.display_name}</h2>
            <span
              className={`status-badge ${
                getPersonDisplayStatus(person) === 'READY'
                  ? 'bg-green-500/10 text-green-400'
                  : getPersonDisplayStatus(person) === 'PROCESSING'
                  ? 'bg-yellow-500/10 text-yellow-400'
                  : 'bg-red-500/10 text-red-400'
              }`}
            >
              {t.people.status[getPersonDisplayStatus(person)]}
            </span>
          </div>
          <button onClick={onClose} className="text-surface-400 hover:text-surface-200">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Photos Section */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-surface-200">{t.people.photoList}</h3>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="btn btn-secondary text-sm"
            >
              {uploading ? t.people.uploadingPhotos : t.people.addPhotos}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => handlePhotoUpload(e.target.files)}
              className="hidden"
            />
          </div>

          {/* Uploading Previews */}
          {Object.entries(uploadingPreviews).length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
              {Object.entries(uploadingPreviews).map(([tempId, previewUrl]) => (
                <div
                  key={tempId}
                  className="relative aspect-square rounded-lg overflow-hidden bg-surface-900/50 border border-surface-700/30"
                >
                  <img
                    src={previewUrl}
                    alt="Uploading..."
                    className="w-full h-full object-cover opacity-50"
                  />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-8 h-8 spinner" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Persisted Photos */}
          {person.photos && person.photos.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {person.photos.map((photo) => {
                const state = photoStateConfig[photo.state];
                const thumbnailUrl = signedUrls[photo.id];

                return (
                  <div
                    key={photo.id}
                    className="relative aspect-square rounded-lg overflow-hidden bg-surface-900/50 border border-surface-700/30"
                  >
                    {thumbnailUrl ? (
                      <img
                        src={thumbnailUrl}
                        alt={photo.storage_path.split('/').pop()}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-surface-600">
                        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                      </div>
                    )}

                    {/* Status Badge Overlay */}
                    <div className="absolute top-2 right-2">
                      <span className={`status-badge ${state.color} text-xs`}>
                        {state.label}
                      </span>
                    </div>

                    {/* Quality Score */}
                    {photo.quality_score !== undefined && photo.quality_score !== null && (
                      <div className="absolute bottom-2 left-2">
                        <span className="text-xs bg-black/70 text-white px-2 py-1 rounded">
                          {t.people.qualityScore}: {photo.quality_score.toFixed(2)}
                        </span>
                      </div>
                    )}

                    {/* Error Message */}
                    {photo.error_message && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-2">
                        <p className="text-xs text-red-400 text-center">{photo.error_message}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : !uploading && Object.entries(uploadingPreviews).length === 0 ? (
            <div className="text-center py-8 text-surface-400">
              <p className="mb-2">{t.people.noPhotos}</p>
              <p className="text-sm">{t.people.uploadFirstPhoto}</p>
            </div>
          ) : null}
        </div>

        <button onClick={onClose} className="btn btn-primary w-full">
          {t.people.close}
        </button>
      </div>
    </div>
  );
}
