'use client';

import { useState, useRef } from 'react';
import type { SelectedScene } from './highlightReelUtils';
import { formatDuration } from './highlightReelUtils';
import { useLanguage } from '@/lib/i18n';

interface SelectionTrayProps {
  selected: SelectedScene[];
  onRemove: (sceneId: string) => void;
  onClear: () => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
  onExport: () => void;
  totalDurationS: number;
  isExporting?: boolean;
  className?: string;
}

/**
 * SelectionTray component for displaying and managing selected scenes.
 * Supports drag-and-drop reordering on desktop and up/down buttons for all devices.
 *
 * @param {SelectionTrayProps} props - Component props.
 * @param {SelectedScene[]} props.selected - List of selected scenes.
 * @param {(sceneId: string) => void} props.onRemove - Callback to remove a scene.
 * @param {() => void} props.onClear - Callback to clear all scenes.
 * @param {(fromIndex: number, toIndex: number) => void} props.onReorder - Callback to reorder scenes.
 * @param {() => void} props.onExport - Callback to trigger export.
 * @param {number} props.totalDurationS - Total duration of selected scenes in seconds.
 * @param {boolean} [props.isExporting=false] - Whether an export is currently in progress.
 * @param {string} [props.className] - Optional CSS class.
 * @returns {JSX.Element | null} Rendered selection tray or null if no scenes selected.
 */
export function SelectionTray({
  selected,
  onRemove,
  onClear,
  onReorder,
  onExport,
  totalDurationS,
  isExporting = false,
  className = '',
}: SelectionTrayProps) {
  const { t } = useLanguage();
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const dragNodeRef = useRef<HTMLDivElement | null>(null);

  if (selected.length === 0) {
    return null;
  }

  // Drag handlers for HTML5 drag-and-drop
  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    dragNodeRef.current = e.currentTarget as HTMLDivElement;
    e.dataTransfer.effectAllowed = 'move';
    // Add a small delay to allow the drag image to render
    setTimeout(() => {
      if (dragNodeRef.current) {
        dragNodeRef.current.classList.add('opacity-50');
      }
    }, 0);
  };

  const handleDragEnd = () => {
    if (dragNodeRef.current) {
      dragNodeRef.current.classList.remove('opacity-50');
    }
    setDraggedIndex(null);
    setDragOverIndex(null);
    dragNodeRef.current = null;
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, toIndex: number) => {
    e.preventDefault();
    if (draggedIndex !== null && draggedIndex !== toIndex) {
      onReorder(draggedIndex, toIndex);
    }
    handleDragEnd();
  };

  // Button-based reorder for accessibility/mobile
  const handleMoveUp = (index: number) => {
    if (index > 0) {
      onReorder(index, index - 1);
    }
  };

  const handleMoveDown = (index: number) => {
    if (index < selected.length - 1) {
      onReorder(index, index + 1);
    }
  };

  return (
    <div className={`card ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-surface-100">
            {t.highlightReel?.selectedScenes || 'Selected Scenes'} ({selected.length})
          </h3>
          <span className="text-xs text-surface-500">
            {t.highlightReel?.totalDuration || 'Total'}: {formatDuration(totalDurationS)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onClear}
            className="px-2 py-1 text-xs font-medium rounded bg-surface-800/50 border border-surface-700/30 text-surface-400 hover:bg-surface-700/50 hover:border-surface-600 hover:text-surface-300 transition-all"
          >
            {t.highlightReel?.clear || 'Clear'}
          </button>
          <button
            onClick={onExport}
            disabled={isExporting}
            className="px-3 py-1 text-xs font-medium rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {isExporting && <div className="w-3 h-3 spinner" />}
            {t.highlightReel?.export || 'Export'}
          </button>
        </div>
      </div>

      {/* Scene List */}
      <div className="space-y-2 max-h-48 overflow-y-auto no-scrollbar">
        {selected.map((scene, index) => (
          <div
            key={scene.scene_id}
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragEnd={handleDragEnd}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
            className={`
              flex items-center gap-2 p-2 rounded-lg bg-surface-800/50 border transition-all
              ${dragOverIndex === index
                ? 'border-accent-cyan bg-accent-cyan/10'
                : 'border-surface-700/30 hover:border-surface-600'
              }
              ${draggedIndex === index ? 'opacity-50' : ''}
              cursor-grab active:cursor-grabbing
            `}
          >
            {/* Drag Handle */}
            <div className="flex-shrink-0 text-surface-600 hover:text-surface-400 cursor-grab">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="9" cy="6" r="1.5" />
                <circle cx="15" cy="6" r="1.5" />
                <circle cx="9" cy="12" r="1.5" />
                <circle cx="15" cy="12" r="1.5" />
                <circle cx="9" cy="18" r="1.5" />
                <circle cx="15" cy="18" r="1.5" />
              </svg>
            </div>

            {/* Thumbnail */}
            {scene.thumbnail_url ? (
              <div className="flex-shrink-0 w-12 h-8 rounded overflow-hidden bg-surface-900">
                <img
                  src={scene.thumbnail_url}
                  alt=""
                  className="w-full h-full object-cover"
                />
              </div>
            ) : (
              <div className="flex-shrink-0 w-12 h-8 rounded bg-surface-900 flex items-center justify-center">
                <svg className="w-4 h-4 text-surface-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
            )}

            {/* Scene Info */}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-surface-300 truncate">
                {scene.video_filename}
              </div>
              <div className="text-[10px] text-surface-500">
                {t.search?.scene || 'Scene'} {scene.index + 1} &bull; {scene.start_s.toFixed(1)}s - {scene.end_s.toFixed(1)}s
              </div>
            </div>

            {/* Up/Down Buttons (for accessibility) */}
            <div className="flex flex-col gap-0.5">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleMoveUp(index);
                }}
                disabled={index === 0}
                className="p-0.5 text-surface-500 hover:text-surface-300 disabled:opacity-30 disabled:cursor-not-allowed"
                title={t.highlightReel?.moveUp || 'Move up'}
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="18 15 12 9 6 15" />
                </svg>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleMoveDown(index);
                }}
                disabled={index === selected.length - 1}
                className="p-0.5 text-surface-500 hover:text-surface-300 disabled:opacity-30 disabled:cursor-not-allowed"
                title={t.highlightReel?.moveDown || 'Move down'}
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
            </div>

            {/* Remove Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove(scene.scene_id);
              }}
              className="flex-shrink-0 p-1 text-surface-500 hover:text-status-error transition-colors"
              title={t.highlightReel?.remove || 'Remove'}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Hint */}
      <div className="mt-2 text-[10px] text-surface-600">
        {t.highlightReel?.reorderHint || 'Drag to reorder or use arrows'}
      </div>
    </div>
  );
}
