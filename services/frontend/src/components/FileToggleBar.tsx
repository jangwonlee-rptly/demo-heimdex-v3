'use client';

import type { GroupedFile } from './fileToggleUtils';

interface FileToggleBarProps {
  files: GroupedFile[];
  toggles: Record<string, boolean>;
  onToggle: (videoId: string) => void;
  onAll: () => void;
  onNone: () => void;
  totalScenes: number;
  className?: string;
}

/**
 * FileToggleBar component for filtering search results by video file.
 * Displays a horizontal list of toggleable file chips.
 */
export function FileToggleBar({
  files,
  toggles,
  onToggle,
  onAll,
  onNone,
  totalScenes,
  className = '',
}: FileToggleBarProps) {
  if (files.length === 0) {
    return null;
  }

  const enabledCount = files.filter((f) => toggles[f.videoId] !== false).length;
  const visibleSceneCount = files
    .filter((f) => toggles[f.videoId] !== false)
    .reduce((sum, f) => sum + f.sceneCount, 0);

  return (
    <div className={`card ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-surface-100">Filter by File</h3>
          <span className="text-xs text-surface-500">
            Showing {enabledCount}/{files.length} files, {visibleSceneCount}/{totalScenes} scenes
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onAll}
            className="px-2 py-1 text-xs font-medium rounded bg-surface-800/50 border border-surface-700/30 text-surface-400 hover:bg-surface-700/50 hover:border-surface-600 hover:text-surface-300 transition-all"
          >
            All
          </button>
          <button
            onClick={onNone}
            className="px-2 py-1 text-xs font-medium rounded bg-surface-800/50 border border-surface-700/30 text-surface-400 hover:bg-surface-700/50 hover:border-surface-600 hover:text-surface-300 transition-all"
          >
            None
          </button>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2">
        {files.map((file) => {
          const isEnabled = toggles[file.videoId] !== false;

          return (
            <button
              key={file.videoId}
              onClick={() => onToggle(file.videoId)}
              className={`
                flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all
                ${
                  isEnabled
                    ? 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20'
                    : 'bg-surface-800/30 border-surface-700/20 text-surface-600 hover:bg-surface-800/50 opacity-60'
                }
              `}
              title={`${file.filename} (${file.sceneCount} scenes) - Click to ${isEnabled ? 'hide' : 'show'}`}
            >
              <span className={isEnabled ? '' : 'line-through'}>
                {file.filename}
              </span>
              <span className="ml-1.5 opacity-75">({file.sceneCount})</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
