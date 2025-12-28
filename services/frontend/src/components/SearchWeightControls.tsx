'use client';

import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';

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
 *
 * @param {SearchWeightControlsProps} props - Component props.
 * @param {(state: WeightState) => void} props.onChange - Callback when weight state changes.
 * @param {string} [props.className] - Optional CSS class for the container.
 * @returns {JSX.Element} Rendered search weight controls.
 */
export function SearchWeightControls({ onChange, className = '' }: SearchWeightControlsProps) {
  const { t } = useLanguage();
  const [savedWeights, setSavedWeights] = useState<Weights | null>(null);
  const [weights, setWeights] = useState<Weights>(SYSTEM_DEFAULTS);
  const [useSaved, setUseSaved] = useState(true);
  const [isOverride, setIsOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [showToast, setShowToast] = useState(false);

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
    // Show toast if user tries to modify while using saved defaults
    if (useSaved) {
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      return;
    }

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
    // Show toast if user tries to modify while using saved defaults
    if (useSaved) {
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      return;
    }

    const preset = PRESETS[presetName];
    setWeights(preset);
    setUseSaved(false);
    setIsOverride(true);
    setStatusMessage(`${t.searchWeights.appliedPreset}: ${presetName}`);
    setTimeout(() => setStatusMessage(''), 2000);
  };

  const handleToggleUseSaved = () => {
    const newUseSaved = !useSaved;
    setUseSaved(newUseSaved);

    if (newUseSaved) {
      // Switch to saved or defaults
      setWeights(savedWeights || SYSTEM_DEFAULTS);
      setIsOverride(false);
      setStatusMessage(savedWeights ? t.searchWeights.usingSaved : t.searchWeights.usingSystem);
    } else {
      // Keep current weights but mark as override
      setIsOverride(true);
      setStatusMessage(t.searchWeights.customActive);
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
      setStatusMessage(t.searchWeights.savedAsDefault);
      setTimeout(() => setStatusMessage(''), 2000);
    } catch (error) {
      console.error('Failed to save preferences:', error);
      setStatusMessage(t.searchWeights.failedToSave);
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
      setStatusMessage(t.searchWeights.resetToSaved);
    } else {
      setWeights(SYSTEM_DEFAULTS);
      setUseSaved(true);
      setIsOverride(false);
      setStatusMessage(t.searchWeights.resetToSystem);
    }
    setTimeout(() => setStatusMessage(''), 2000);
  };

  if (loading) {
    return (
      <div className={`card ${className}`}>
        <div className="flex items-center gap-2 text-surface-500">
          <div className="w-4 h-4 spinner" />
          <span className="text-sm">{t.searchWeights.loadingPreferences}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`card ${className} relative`}>
      {/* Toast Notification */}
      {showToast && (
        <div className="absolute top-4 right-4 z-50 animate-fade-in">
          <div className="px-4 py-2 rounded-lg bg-surface-800 border border-accent-cyan/30 shadow-lg flex items-center gap-2">
            <svg className="w-4 h-4 text-accent-cyan flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="text-xs text-surface-200">
              {t.searchWeights.modifyHint}
            </span>
          </div>
        </div>
      )}

      {/* Header with collapse button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-4 group"
      >
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-surface-100">{t.searchWeights.title}</h3>
          {!isExpanded && (
            <span className="text-xs text-surface-500">
              {useSaved ? `(${t.searchWeights.usingSavedDefaults})` : `(${t.searchWeights.custom})`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {statusMessage && (
            <span className="text-xs text-accent-cyan">{statusMessage}</span>
          )}
          <svg
            className={`w-5 h-5 text-surface-400 group-hover:text-surface-300 transition-transform ${
              isExpanded ? 'rotate-180' : ''
            }`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {/* Collapsible content */}
      {isExpanded && (
        <div className="space-y-4">
          {/* Sliders */}
          <div className="space-y-3">
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
                />
              </div>
            ))}
          </div>

          {/* Presets */}
          <div>
            <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">
              {t.searchWeights.presets}
            </p>
            <div className="grid grid-cols-4 gap-2">
              {Object.keys(PRESETS).map((presetName) => (
                <button
                  key={presetName}
                  onClick={() => handlePresetClick(presetName)}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-800/50 border border-surface-700/30 text-surface-300 hover:bg-surface-700/50 hover:border-accent-cyan/30 hover:text-accent-cyan transition-all capitalize"
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
                {t.searchWeights.useSavedDefaults}
              </span>
            </label>

            <div className="flex gap-2">
              <button
                onClick={handleReset}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-800/50 border border-surface-700/30 text-surface-400 hover:bg-surface-700/50 hover:border-surface-600 hover:text-surface-300 transition-all"
              >
                {t.searchWeights.reset}
              </button>
              <button
                onClick={handleSaveAsDefault}
                disabled={saving || useSaved}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {saving && <div className="w-3 h-3 spinner" />}
                {t.searchWeights.saveAsDefault}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
