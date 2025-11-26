/**
 * Utility functions for normalizing search signal weights.
 *
 * Core constraint: All weights must sum to exactly 1.0 (within epsilon tolerance).
 *
 * Normalization algorithm:
 * 1. When a user adjusts one signal's weight, we need to redistribute the difference
 *    across other unlocked signals to maintain sum = 1.0
 * 2. The redistribution is proportional to each signal's current weight
 *    (signals with higher weights absorb more of the change).
 * 3. If a signal would go below 0 or above 1, we clamp it and redistribute to others.
 * 4. Locked signals are never adjusted during normalization.
 *
 * @module normalizeWeights
 */

export type SearchSignalKey = 'asr' | 'image' | 'metadata' | string;

export type SignalWeight = {
  key: SearchSignalKey;
  weight: number; // 0–1, sum of all = 1
  locked?: boolean; // if true, this weight won't be auto-adjusted
};

/** Epsilon for floating-point comparison */
const EPSILON = 1e-6;

/**
 * Check if weights sum to 1.0 within epsilon tolerance.
 */
export function isNormalized(weights: SignalWeight[]): boolean {
  const sum = weights.reduce((acc, w) => acc + w.weight, 0);
  return Math.abs(sum - 1.0) < EPSILON;
}

/**
 * Get the sum of all weights.
 */
export function getWeightsSum(weights: SignalWeight[]): number {
  return weights.reduce((acc, w) => acc + w.weight, 0);
}

/**
 * Clamp a value between min and max.
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Normalize weights to sum to exactly 1.0.
 *
 * Strategy:
 * 1. Calculate the current sum
 * 2. If sum is 0, distribute evenly across all unlocked signals
 * 3. Otherwise, scale each unlocked signal proportionally to reach sum = 1
 * 4. Handle edge cases (all locked, single signal, etc.)
 *
 * @param weights - Array of signal weights
 * @returns Normalized weights that sum to 1.0
 */
export function normalizeWeights(weights: SignalWeight[]): SignalWeight[] {
  if (weights.length === 0) return [];

  // Find locked and unlocked signals
  const locked = weights.filter(w => w.locked);
  const unlocked = weights.filter(w => !w.locked);

  // If all signals are locked, we can't normalize - return as-is
  if (unlocked.length === 0) {
    return weights.map(w => ({ ...w }));
  }

  const lockedSum = locked.reduce((sum, w) => sum + w.weight, 0);
  const unlockedSum = unlocked.reduce((sum, w) => sum + w.weight, 0);
  const targetUnlockedSum = 1.0 - lockedSum;

  // If locked signals already exceed 1.0, we have a problem
  // Scale down locked signals proportionally (emergency case)
  if (lockedSum > 1.0 + EPSILON) {
    const scale = 1.0 / lockedSum;
    return weights.map(w => ({
      ...w,
      weight: clamp(w.weight * scale, 0, 1)
    }));
  }

  // If target for unlocked is negative or zero, set all unlocked to 0
  if (targetUnlockedSum <= EPSILON) {
    return weights.map(w => ({
      ...w,
      weight: w.locked ? w.weight : 0
    }));
  }

  // If unlocked sum is 0, distribute target evenly
  if (unlockedSum < EPSILON) {
    const evenWeight = targetUnlockedSum / unlocked.length;
    return weights.map(w => ({
      ...w,
      weight: w.locked ? w.weight : evenWeight
    }));
  }

  // Scale unlocked weights proportionally to reach target sum
  const scale = targetUnlockedSum / unlockedSum;
  return weights.map(w => ({
    ...w,
    weight: w.locked ? w.weight : clamp(w.weight * scale, 0, 1)
  }));
}

/**
 * Update a single signal's weight and normalize the rest.
 *
 * This is the key function for interactive slider adjustment.
 *
 * Algorithm:
 * 1. Update the target signal to the new weight
 * 2. Calculate the difference from the old weight
 * 3. Distribute this difference across other unlocked signals proportionally
 * 4. If any signal would go out of bounds, clamp and redistribute remainder
 *
 * @param weights - Current weights
 * @param targetKey - The signal being adjusted
 * @param newWeight - The new weight for the target signal (0-1)
 * @returns Updated and normalized weights
 */
export function updateWeight(
  weights: SignalWeight[],
  targetKey: SearchSignalKey,
  newWeight: number
): SignalWeight[] {
  // Clamp the new weight
  newWeight = clamp(newWeight, 0, 1);

  // Find the target signal
  const targetIndex = weights.findIndex(w => w.key === targetKey);
  if (targetIndex === -1) {
    return weights.map(w => ({ ...w }));
  }

  const oldWeight = weights[targetIndex].weight;
  const delta = newWeight - oldWeight;

  // If no change, return as-is
  if (Math.abs(delta) < EPSILON) {
    return weights.map(w => ({ ...w }));
  }

  // Find other unlocked signals to adjust
  const others = weights
    .map((w, idx) => ({ ...w, index: idx }))
    .filter((w, idx) => idx !== targetIndex && !w.locked);

  // If no others to adjust, we can't maintain sum = 1
  // Normalize after setting the new weight
  if (others.length === 0) {
    const updated = weights.map((w, idx) => ({
      ...w,
      weight: idx === targetIndex ? newWeight : w.weight
    }));
    return normalizeWeights(updated);
  }

  // Calculate total weight of adjustable signals
  const othersSum = others.reduce((sum, w) => sum + w.weight, 0);

  // Create updated weights array
  const updated = weights.map((w, idx) => {
    if (idx === targetIndex) {
      return { ...w, weight: newWeight };
    }
    if (w.locked) {
      return { ...w };
    }

    // Distribute the delta proportionally
    if (othersSum > EPSILON) {
      const proportion = w.weight / othersSum;
      const adjustment = -delta * proportion;
      return { ...w, weight: clamp(w.weight + adjustment, 0, 1) };
    } else {
      // If others sum to 0, distribute evenly
      const evenDistribution = -delta / others.length;
      return { ...w, weight: clamp(evenDistribution, 0, 1) };
    }
  });

  // Final normalization pass to handle any rounding errors or clamping effects
  return normalizeWeights(updated);
}

/**
 * Apply a preset configuration to weights.
 *
 * @param weights - Current weights structure (to preserve keys and locked state)
 * @param preset - Record of key -> weight values that sum to 1.0
 * @returns Updated weights with preset values applied
 */
export function applyPreset(
  weights: SignalWeight[],
  preset: Record<SearchSignalKey, number>
): SignalWeight[] {
  // Apply preset values, keeping locked state
  const updated = weights.map(w => ({
    ...w,
    weight: preset[w.key] !== undefined ? preset[w.key] : w.weight
  }));

  // Normalize to ensure sum = 1.0
  return normalizeWeights(updated);
}

/**
 * Round weight to nearest step (e.g., 0.05 for 5% increments).
 *
 * @param weight - Raw weight value
 * @param step - Step size (e.g., 0.05 for 5%)
 * @returns Rounded weight
 */
export function roundToStep(weight: number, step: number = 0.05): number {
  return Math.round(weight / step) * step;
}

/**
 * Convert weight (0-1) to percentage string (0-100%).
 *
 * @param weight - Weight value 0-1
 * @param decimals - Number of decimal places
 * @returns Formatted percentage string
 */
export function weightToPercentage(weight: number, decimals: number = 0): string {
  return `${(weight * 100).toFixed(decimals)}%`;
}

/**
 * Convert percentage (0-100) to weight (0-1).
 *
 * @param percentage - Percentage value 0-100
 * @returns Weight value 0-1
 */
export function percentageToWeight(percentage: number): number {
  return clamp(percentage / 100, 0, 1);
}
