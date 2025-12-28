'use client';

import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/supabase';

export type Weights = {
  transcript: number;
  visual: number;
  summary: number;
  lexical: number;
};

export interface WeightState {
  weights: Weights;
  useSaved: boolean;
  isOverride: boolean;
}

interface SearchWeightControlsProps {
  onChange: (state: WeightState) => void;
  className?: string;
}

interface PreferencesResponse {
  channel_weights: {
    transcript: number;
    visual: number;
    summary: number;
    lexical: number;
  };
  fusion_method: string;
  visual_mode: string;
}

// System default weights
const SYSTEM_DEFAULTS: Weights = {
  transcript: 0.45,
  visual: 0.25,
  summary: 0.10,
  lexical: 0.20,
};

// Preset configurations
const PRESETS: Record<string, Weights> = {
  balanced: { transcript: 0.45, visual: 0.25, summary: 0.10, lexical: 0.20 },
  visual: { transcript: 0.20, visual: 0.50, summary: 0.15, lexical: 0.15 },
  dialogue: { transcript: 0.60, visual: 0.15, summary: 0.10, lexical: 0.15 },
  keywords: { transcript: 0.25, visual: 0.15, summary: 0.10, lexical: 0.50 },
};

/**
 * Validates and normalizes weights to sum to 1.0.
 * Warns in dev mode if drift is significant.
 */
function assertWeightsSum(weights: Weights): Weights {
  const sum = weights.transcript + weights.visual + weights.summary + weights.lexical;

  if (Math.abs(sum - 1.0) > 0.01) {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`[SearchWeightControls] Weight sum drift detected: ${sum.toFixed(4)}, renormalizing...`);
    }
    // Renormalize
    return {
      transcript: weights.transcript / sum,
      visual: weights.visual / sum,
      summary: weights.summary / sum,
      lexical: weights.lexical / sum,
    };
  }

  return weights;
}

/**
 * Component for managing search channel weights.
 * Supports user-customizable weights, presets, and saved defaults.
 */
export function SearchWeightControls({ onChange, className = '' }: SearchWeightControlsProps) {
  const [savedWeights, setSavedWeights] = useState<Weights | null>(null);
  const [weights, setWeights] = useState<Weights>(SYSTEM_DEFAULTS);
  const [useSaved, setUseSaved] = useState(true);
  const [isOverride, setIsOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');

  // Load saved preferences on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const prefs = await apiRequest<PreferencesResponse>('/preferences/search', {
          method: 'GET',
        });

        const loadedWeights: Weights = {
          transcript: prefs.channel_weights.transcript,
          visual: prefs.channel_weights.visual,
          summary: prefs.channel_weights.summary,
          lexical: prefs.channel_weights.lexical,
        };

        setSavedWeights(loadedWeights);
        setWeights(loadedWeights);
        setUseSaved(true);
        setIsOverride(false);
      } catch (error) {
        // No saved preferences or error - use system defaults
        console.log('No saved preferences, using system defaults');
        setSavedWeights(null);
        setWeights(SYSTEM_DEFAULTS);
        setUseSaved(true);
        setIsOverride(false);
      } finally {
        setLoading(false);
      }
    };

    loadPreferences();
  }, []);

  // Notify parent of changes
  useEffect(() => {
    if (!loading) {
      onChange({ weights, useSaved, isOverride });
    }
  }, [weights, useSaved, isOverride, loading, onChange]);

  const handleSliderChange = (channel: keyof Weights, value: number) => {
    const newValue = value / 100; // Convert from 0-100 to 0-1
    const oldValue = weights[channel];
    const diff = newValue - oldValue;

    // Distribute the difference proportionally across other channels
    const otherChannels = (Object.keys(weights) as Array<keyof Weights>).filter(k => k !== channel);
    const otherSum = otherChannels.reduce((sum, k) => sum + weights[k], 0);

    const newWeights: Weights = { ...weights, [channel]: newValue };

    if (otherSum > 0) {
      otherChannels.forEach(k => {
        const proportion = weights[k] / otherSum;
        newWeights[k] = Math.max(0, weights[k] - diff * proportion);
      });
    }

    // Validate and normalize
    const validatedWeights = assertWeightsSum(newWeights);

    setWeights(validatedWeights);
    setUseSaved(false);
    setIsOverride(true);
    setStatusMessage('');
  };

  const handlePresetClick = (presetName: string) => {
    const preset = PRESETS[presetName];
    setWeights(preset);
    setUseSaved(false);
    setIsOverride(true);
    setStatusMessage(`Applied ${presetName} preset`);
    setTimeout(() => setStatusMessage(''), 2000);
  };

  const handleToggleUseSaved = () => {
    const newUseSaved = !useSaved;
    setUseSaved(newUseSaved);

    if (newUseSaved) {
      // Switch to saved or defaults
      setWeights(savedWeights || SYSTEM_DEFAULTS);
      setIsOverride(false);
      setStatusMessage(savedWeights ? 'Using saved defaults' : 'Using system defaults');
    } else {
      // Keep current weights but mark as override
      setIsOverride(true);
      setStatusMessage('Custom weights active');
    }

    setTimeout(() => setStatusMessage(''), 2000);
  };

  const handleSaveAsDefault = async () => {
    setSaving(true);
    setStatusMessage('');

    try {
      await apiRequest('/preferences/search', {
        method: 'PUT',
        body: JSON.stringify({
          channel_weights: {
            transcript: weights.transcript,
            visual: weights.visual,
            summary: weights.summary,
            lexical: weights.lexical,
          },
          fusion_method: 'minmax_mean',
          visual_mode: 'auto',
        }),
      });

      setSavedWeights(weights);
      setUseSaved(true);
      setIsOverride(false);
      setStatusMessage('Saved as default');
      setTimeout(() => setStatusMessage(''), 2000);
    } catch (error) {
      console.error('Failed to save preferences:', error);
      setStatusMessage('Failed to save');
      setTimeout(() => setStatusMessage(''), 3000);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (savedWeights) {
      setWeights(savedWeights);
      setUseSaved(true);
      setIsOverride(false);
      setStatusMessage('Reset to saved defaults');
    } else {
      setWeights(SYSTEM_DEFAULTS);
      setUseSaved(true);
      setIsOverride(false);
      setStatusMessage('Reset to system defaults');
    }
    setTimeout(() => setStatusMessage(''), 2000);
  };

  if (loading) {
    return (
      <div className={`card ${className}`}>
        <div className="flex items-center gap-2 text-surface-500">
          <div className="w-4 h-4 spinner" />
          <span className="text-sm">Loading preferences...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`card ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-surface-100">Search Weights</h3>
        {statusMessage && (
          <span className="text-xs text-accent-cyan">{statusMessage}</span>
        )}
      </div>

      {/* Sliders */}
      <div className="space-y-3 mb-4">
        {(Object.keys(weights) as Array<keyof Weights>).map((channel) => (
          <div key={channel}>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-surface-300 capitalize">
                {channel}
              </label>
              <span className="text-xs font-mono text-surface-500">
                {Math.round(weights[channel] * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights[channel] * 100)}
              onChange={(e) => handleSliderChange(channel, parseInt(e.target.value))}
              className="w-full h-2 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-accent-cyan"
              disabled={useSaved}
            />
          </div>
        ))}
      </div>

      {/* Presets */}
      <div className="mb-4">
        <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
          Presets
        </p>
        <div className="grid grid-cols-4 gap-2">
          {Object.keys(PRESETS).map((presetName) => (
            <button
              key={presetName}
              onClick={() => handlePresetClick(presetName)}
              disabled={useSaved}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-800/50 border border-surface-700/30 text-surface-300 hover:bg-surface-700/50 hover:border-accent-cyan/30 hover:text-accent-cyan transition-all disabled:opacity-50 disabled:cursor-not-allowed capitalize"
            >
              {presetName}
            </button>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between pt-4 border-t border-surface-700/30">
        <label className="flex items-center gap-2 cursor-pointer group">
          <input
            type="checkbox"
            checked={useSaved}
            onChange={handleToggleUseSaved}
            className="w-4 h-4 rounded bg-surface-700 border-surface-600 text-accent-cyan focus:ring-accent-cyan focus:ring-offset-0"
          />
          <span className="text-xs text-surface-400 group-hover:text-surface-300">
            Use my saved defaults
          </span>
        </label>

        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-800/50 border border-surface-700/30 text-surface-400 hover:bg-surface-700/50 hover:border-surface-600 hover:text-surface-300 transition-all"
          >
            Reset
          </button>
          <button
            onClick={handleSaveAsDefault}
            disabled={saving || useSaved}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {saving && <div className="w-3 h-3 spinner" />}
            Save as default
          </button>
        </div>
      </div>
    </div>
  );
}
