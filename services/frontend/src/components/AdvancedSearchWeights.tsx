'use client';

import { useState, useEffect } from 'react';
import {
  SearchSignalKey,
  SignalWeight,
  updateWeight,
  applyPreset,
  normalizeWeights,
  weightToPercentage,
  percentageToWeight,
  getWeightsSum,
  isNormalized,
  roundToStep
} from '@/lib/normalizeWeights';

/**
 * Configuration for a single search signal.
 */
export type SignalConfig = {
  key: SearchSignalKey;
  label: string;
  description?: string;
  color?: string; // Tailwind color class for visual distinction
  min?: number; // default 0
  max?: number; // default 1
};

/**
 * A preset configuration with predefined weights.
 */
export type WeightPreset = {
  id: string;
  label: string;
  description?: string;
  weights: Record<SearchSignalKey, number>; // must sum to 1
};

/**
 * Props for the AdvancedSearchWeights component.
 */
export type AdvancedSearchWeightsProps = {
  /** Signal configurations */
  signals: SignalConfig[];
  /** Current weight values (controlled) */
  value: SignalWeight[];
  /** Callback when weights change */
  onChange: (value: SignalWeight[]) => void;
  /** Optional presets for quick configuration */
  presets?: WeightPreset[];
  /** Step size for slider adjustments (default: 0.05 for 5%) */
  step?: number;
  /** Show advanced features like lock buttons */
  showAdvanced?: boolean;
};

/**
 * Advanced Search Weights Component
 *
 * Allows users to adjust weights for multiple search signals while
 * maintaining the constraint that all weights sum to 1.0.
 *
 * Features:
 * - Interactive sliders with auto-normalization
 * - Preset configurations
 * - Lock individual signals
 * - Visual feedback for total weight
 * - Accessible keyboard navigation
 *
 * @example
 * ```tsx
 * const [weights, setWeights] = useState([
 *   { key: 'asr', weight: 0.4 },
 *   { key: 'image', weight: 0.4 },
 *   { key: 'metadata', weight: 0.2 }
 * ]);
 *
 * <AdvancedSearchWeights
 *   signals={signalConfigs}
 *   value={weights}
 *   onChange={setWeights}
 *   presets={presets}
 * />
 * ```
 */
export default function AdvancedSearchWeights({
  signals,
  value,
  onChange,
  presets = [],
  step = 0.05,
  showAdvanced = false
}: AdvancedSearchWeightsProps) {
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Ensure weights are normalized on mount
  useEffect(() => {
    if (!isNormalized(value)) {
      onChange(normalizeWeights(value));
    }
  }, []); // Only on mount

  /**
   * Handle slider change for a specific signal.
   */
  const handleSliderChange = (key: SearchSignalKey, newValue: number) => {
    const rounded = roundToStep(newValue, step);
    const updated = updateWeight(value, key, rounded);
    onChange(updated);
    setSelectedPreset(null); // Clear preset selection when manually adjusting
  };

  /**
   * Handle direct percentage input.
   */
  const handlePercentageInput = (key: SearchSignalKey, percentage: string) => {
    const numericValue = parseFloat(percentage);
    if (isNaN(numericValue)) return;

    const weight = percentageToWeight(numericValue);
    const updated = updateWeight(value, key, weight);
    onChange(updated);
    setSelectedPreset(null);
  };

  /**
   * Toggle lock state for a signal.
   */
  const handleToggleLock = (key: SearchSignalKey) => {
    const updated = value.map(w =>
      w.key === key ? { ...w, locked: !w.locked } : w
    );
    onChange(updated);
  };

  /**
   * Apply a preset configuration.
   */
  const handleApplyPreset = (preset: WeightPreset) => {
    const updated = applyPreset(value, preset.weights);
    onChange(updated);
    setSelectedPreset(preset.id);
  };

  /**
   * Reset to balanced (equal) weights.
   */
  const handleReset = () => {
    const equalWeight = 1.0 / signals.length;
    const reset = signals.map(s => ({
      key: s.key,
      weight: equalWeight,
      locked: false
    }));
    onChange(reset);
    setSelectedPreset(null);
  };

  // Calculate current sum and check if normalized
  const currentSum = getWeightsSum(value);
  const normalized = isNormalized(value);

  // Create lookup map for signal configs
  const signalMap = new Map(signals.map(s => [s.key, s]));

  return (
    <div className="space-y-6 p-6 bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Advanced Search Weighting
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            Adjust how much each signal contributes to search results
          </p>
        </div>
        <button
          onClick={handleReset}
          className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          aria-label="Reset to balanced weights"
        >
          Reset
        </button>
      </div>

      {/* Presets */}
      {presets.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">
            Quick Presets
          </label>
          <div className="flex flex-wrap gap-2">
            {presets.map(preset => (
              <button
                key={preset.id}
                onClick={() => handleApplyPreset(preset)}
                className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  selectedPreset === preset.id
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
                title={preset.description}
                aria-label={`Apply ${preset.label} preset`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Signal Weights */}
      <div className="space-y-4">
        {value.map(weight => {
          const config = signalMap.get(weight.key);
          if (!config) return null;

          const percentage = Math.round(weight.weight * 100);
          const isLocked = weight.locked || false;

          return (
            <div
              key={weight.key}
              className={`space-y-2 p-4 rounded-lg border ${
                isLocked
                  ? 'bg-gray-50 border-gray-300'
                  : 'bg-white border-gray-200'
              }`}
            >
              {/* Label and Lock Button */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label
                    htmlFor={`slider-${weight.key}`}
                    className="text-sm font-medium text-gray-900"
                  >
                    {config.label}
                  </label>
                  {config.description && (
                    <button
                      className="group relative"
                      aria-label={`Info about ${config.label}`}
                    >
                      <svg
                        className="w-4 h-4 text-gray-400 hover:text-gray-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                          clipRule="evenodd"
                        />
                      </svg>
                      {/* Tooltip */}
                      <span className="invisible group-hover:visible absolute left-6 top-0 w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10">
                        {config.description}
                      </span>
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {/* Percentage Input */}
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step={step * 100}
                      value={percentage}
                      onChange={(e) => handlePercentageInput(weight.key, e.target.value)}
                      disabled={isLocked}
                      className="w-16 px-2 py-1 text-sm text-right border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
                      aria-label={`${config.label} percentage`}
                    />
                    <span className="text-sm font-medium text-gray-700">%</span>
                  </div>
                  {/* Lock Button */}
                  {showAdvanced && (
                    <button
                      onClick={() => handleToggleLock(weight.key)}
                      className={`p-1.5 rounded transition-colors ${
                        isLocked
                          ? 'text-gray-700 bg-gray-200'
                          : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                      }`}
                      aria-label={`${isLocked ? 'Unlock' : 'Lock'} ${config.label}`}
                      title={isLocked ? 'Locked - won\'t auto-adjust' : 'Unlocked - will auto-adjust'}
                    >
                      {isLocked ? (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 2a5 5 0 00-5 5v2a2 2 0 00-2 2v5a2 2 0 002 2h10a2 2 0 002-2v-5a2 2 0 00-2-2H7V7a3 3 0 015.905-.75 1 1 0 001.937-.5A5.002 5.002 0 0010 2z" />
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* Slider */}
              <div className="relative">
                <input
                  type="range"
                  id={`slider-${weight.key}`}
                  min={config.min || 0}
                  max={config.max || 1}
                  step={step}
                  value={weight.weight}
                  onChange={(e) => handleSliderChange(weight.key, parseFloat(e.target.value))}
                  disabled={isLocked}
                  className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${
                    isLocked ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                  style={{
                    background: isLocked
                      ? '#e5e7eb'
                      : `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`
                  }}
                  aria-label={`${config.label} weight slider`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percentage}
                  aria-valuetext={`${percentage}%`}
                />
              </div>

              {/* Optional description below slider */}
              {config.description && (
                <p className="text-xs text-gray-500">
                  {config.description}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Total Display */}
      <div className="pt-4 border-t border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">
            Total Weight:
          </span>
          <div className="flex items-center gap-2">
            <span
              className={`text-lg font-semibold ${
                normalized ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {weightToPercentage(currentSum, 1)}
            </span>
            {!normalized && (
              <span className="text-xs text-red-600" role="alert">
                (adjusting...)
              </span>
            )}
            {normalized && (
              <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </div>
        </div>
        {!normalized && (
          <p className="text-xs text-gray-500 mt-1">
            Weights are being automatically adjusted to sum to 100%
          </p>
        )}
      </div>

      {/* Helper Text */}
      <div className="pt-2 text-xs text-gray-500 space-y-1">
        <p>
          💡 <strong>Tip:</strong> Adjust any slider and others will auto-balance to maintain 100% total.
        </p>
        {showAdvanced && (
          <p>
            🔒 <strong>Lock signals</strong> to prevent them from auto-adjusting when you change others.
          </p>
        )}
      </div>
    </div>
  );
}
