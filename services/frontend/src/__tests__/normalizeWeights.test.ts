/**
 * Unit tests for weight normalization utilities.
 *
 * These tests ensure that:
 * 1. Weights always sum to 1.0
 * 2. Normalization is predictable and stable
 * 3. Edge cases are handled correctly
 * 4. Locked signals are respected
 */

import {
  SignalWeight,
  normalizeWeights,
  updateWeight,
  applyPreset,
  isNormalized,
  getWeightsSum,
  roundToStep,
  weightToPercentage,
  percentageToWeight
} from '../lib/normalizeWeights';

describe('normalizeWeights', () => {
  describe('isNormalized', () => {
    test('returns true for weights that sum to 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      expect(isNormalized(weights)).toBe(true);
    });

    test('returns false for weights that do not sum to 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.5 },
        { key: 'image', weight: 0.5 },
        { key: 'metadata', weight: 0.5 }
      ];
      expect(isNormalized(weights)).toBe(false);
    });

    test('handles floating point precision within epsilon', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.333333 },
        { key: 'image', weight: 0.333333 },
        { key: 'metadata', weight: 0.333334 }
      ];
      expect(isNormalized(weights)).toBe(true);
    });
  });

  describe('getWeightsSum', () => {
    test('calculates correct sum', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.3 },
        { key: 'image', weight: 0.5 },
        { key: 'metadata', weight: 0.2 }
      ];
      expect(getWeightsSum(weights)).toBe(1.0);
    });

    test('returns 0 for empty array', () => {
      expect(getWeightsSum([])).toBe(0);
    });
  });

  describe('normalizeWeights', () => {
    test('normalizes weights that sum to more than 1', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.6 },
        { key: 'image', weight: 0.6 },
        { key: 'metadata', weight: 0.3 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      // Should scale down proportionally
      expect(normalized[0].weight).toBeCloseTo(0.4);
      expect(normalized[1].weight).toBeCloseTo(0.4);
      expect(normalized[2].weight).toBeCloseTo(0.2);
    });

    test('normalizes weights that sum to less than 1', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.2 },
        { key: 'image', weight: 0.2 },
        { key: 'metadata', weight: 0.1 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      // Should scale up proportionally
      expect(normalized[0].weight).toBeCloseTo(0.4);
      expect(normalized[1].weight).toBeCloseTo(0.4);
      expect(normalized[2].weight).toBeCloseTo(0.2);
    });

    test('handles all weights at 0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0 },
        { key: 'image', weight: 0 },
        { key: 'metadata', weight: 0 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      // Should distribute evenly
      expect(normalized[0].weight).toBeCloseTo(0.333333, 5);
      expect(normalized[1].weight).toBeCloseTo(0.333333, 5);
      expect(normalized[2].weight).toBeCloseTo(0.333333, 5);
    });

    test('respects locked signals', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.5, locked: true },
        { key: 'image', weight: 0.3 },
        { key: 'metadata', weight: 0.1 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      // Locked signal stays at 0.5
      expect(normalized[0].weight).toBe(0.5);
      // Others normalize to fill remaining 0.5
      expect(normalized[1].weight).toBeCloseTo(0.375); // 0.3 * (0.5 / 0.4)
      expect(normalized[2].weight).toBeCloseTo(0.125); // 0.1 * (0.5 / 0.4)
    });

    test('handles multiple locked signals', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.3, locked: true },
        { key: 'image', weight: 0.4, locked: true },
        { key: 'metadata', weight: 0.5 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      expect(normalized[0].weight).toBe(0.3);
      expect(normalized[1].weight).toBe(0.4);
      expect(normalized[2].weight).toBeCloseTo(0.3); // Fills remainder
    });

    test('handles locked signals exceeding 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.6, locked: true },
        { key: 'image', weight: 0.6, locked: true },
        { key: 'metadata', weight: 0.2 }
      ];
      const normalized = normalizeWeights(weights);
      expect(isNormalized(normalized)).toBe(true);
      // Should scale down locked signals proportionally (emergency case)
      expect(getWeightsSum(normalized)).toBeCloseTo(1.0);
    });

    test('returns empty array for empty input', () => {
      expect(normalizeWeights([])).toEqual([]);
    });
  });

  describe('updateWeight', () => {
    test('updates single weight and normalizes others proportionally', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const updated = updateWeight(weights, 'asr', 0.6);
      expect(isNormalized(updated)).toBe(true);
      expect(updated[0].weight).toBeCloseTo(0.6);
      // Others should decrease proportionally
      // Delta = 0.6 - 0.4 = 0.2
      // Remaining 0.6 should be split 2:1 (image:metadata)
      expect(updated[1].weight).toBeCloseTo(0.267, 2); // 0.4 * (0.4/0.6)
      expect(updated[2].weight).toBeCloseTo(0.133, 2); // 0.2 * (0.4/0.6)
    });

    test('handles increasing weight to 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const updated = updateWeight(weights, 'asr', 1.0);
      expect(isNormalized(updated)).toBe(true);
      expect(updated[0].weight).toBeCloseTo(1.0);
      expect(updated[1].weight).toBeCloseTo(0.0);
      expect(updated[2].weight).toBeCloseTo(0.0);
    });

    test('handles decreasing weight to 0.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const updated = updateWeight(weights, 'asr', 0.0);
      expect(isNormalized(updated)).toBe(true);
      expect(updated[0].weight).toBeCloseTo(0.0);
      // Others should increase proportionally
      expect(updated[1].weight).toBeCloseTo(0.667, 2);
      expect(updated[2].weight).toBeCloseTo(0.333, 2);
    });

    test('respects locked signals when updating', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4, locked: true },
        { key: 'metadata', weight: 0.2 }
      ];
      const updated = updateWeight(weights, 'asr', 0.6);
      expect(isNormalized(updated)).toBe(true);
      expect(updated[0].weight).toBeCloseTo(0.6);
      expect(updated[1].weight).toBeCloseTo(0.4); // Locked, unchanged
      // Metadata must absorb all the delta
      expect(updated[2].weight).toBeCloseTo(0.0);
    });

    test('handles non-existent key gracefully', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.5 },
        { key: 'image', weight: 0.5 }
      ];
      const updated = updateWeight(weights, 'nonexistent', 0.3);
      expect(updated).toEqual(weights);
    });

    test('clamps values above 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.5 },
        { key: 'image', weight: 0.5 }
      ];
      const updated = updateWeight(weights, 'asr', 1.5);
      expect(updated[0].weight).toBeLessThanOrEqual(1.0);
      expect(isNormalized(updated)).toBe(true);
    });

    test('clamps values below 0.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.5 },
        { key: 'image', weight: 0.5 }
      ];
      const updated = updateWeight(weights, 'asr', -0.5);
      expect(updated[0].weight).toBeGreaterThanOrEqual(0.0);
      expect(isNormalized(updated)).toBe(true);
    });
  });

  describe('applyPreset', () => {
    test('applies preset weights correctly', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const preset = {
        asr: 0.7,
        image: 0.2,
        metadata: 0.1
      };
      const updated = applyPreset(weights, preset);
      expect(isNormalized(updated)).toBe(true);
      expect(updated[0].weight).toBeCloseTo(0.7);
      expect(updated[1].weight).toBeCloseTo(0.2);
      expect(updated[2].weight).toBeCloseTo(0.1);
    });

    test('handles partial preset (missing keys)', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const preset = {
        asr: 0.6,
        image: 0.3
        // metadata missing
      };
      const updated = applyPreset(weights, preset);
      expect(isNormalized(updated)).toBe(true);
      // Metadata keeps old value, but everything gets normalized
      expect(updated[0].weight).toBeCloseTo(0.545, 2); // Normalized from 0.6
      expect(updated[1].weight).toBeCloseTo(0.273, 2); // Normalized from 0.3
      expect(updated[2].weight).toBeCloseTo(0.182, 2); // Normalized from 0.2
    });

    test('normalizes preset that does not sum to 1.0', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const preset = {
        asr: 0.5,
        image: 0.5,
        metadata: 0.5
      };
      const updated = applyPreset(weights, preset);
      expect(isNormalized(updated)).toBe(true);
      // Should normalize proportionally
      expect(updated[0].weight).toBeCloseTo(0.333, 2);
      expect(updated[1].weight).toBeCloseTo(0.333, 2);
      expect(updated[2].weight).toBeCloseTo(0.333, 2);
    });

    test('preserves locked state when applying preset', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4, locked: true },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];
      const preset = {
        asr: 0.6,
        image: 0.3,
        metadata: 0.1
      };
      const updated = applyPreset(weights, preset);
      expect(updated[0].locked).toBe(true);
    });
  });

  describe('roundToStep', () => {
    test('rounds to nearest step', () => {
      expect(roundToStep(0.123, 0.05)).toBeCloseTo(0.10);
      expect(roundToStep(0.127, 0.05)).toBeCloseTo(0.15);
      expect(roundToStep(0.342, 0.1)).toBeCloseTo(0.3);
      expect(roundToStep(0.367, 0.1)).toBeCloseTo(0.4);
    });

    test('handles exact multiples', () => {
      expect(roundToStep(0.5, 0.05)).toBe(0.5);
      expect(roundToStep(0.25, 0.05)).toBe(0.25);
    });

    test('handles edge cases', () => {
      expect(roundToStep(0.0, 0.05)).toBe(0.0);
      expect(roundToStep(1.0, 0.05)).toBe(1.0);
    });
  });

  describe('weightToPercentage', () => {
    test('converts weight to percentage string', () => {
      expect(weightToPercentage(0.5)).toBe('50%');
      expect(weightToPercentage(0.333)).toBe('33%');
      expect(weightToPercentage(1.0)).toBe('100%');
      expect(weightToPercentage(0.0)).toBe('0%');
    });

    test('respects decimal places', () => {
      expect(weightToPercentage(0.333, 1)).toBe('33.3%');
      expect(weightToPercentage(0.333, 2)).toBe('33.30%');
    });
  });

  describe('percentageToWeight', () => {
    test('converts percentage to weight', () => {
      expect(percentageToWeight(50)).toBe(0.5);
      expect(percentageToWeight(33.3)).toBeCloseTo(0.333);
      expect(percentageToWeight(100)).toBe(1.0);
      expect(percentageToWeight(0)).toBe(0.0);
    });

    test('clamps out-of-range values', () => {
      expect(percentageToWeight(150)).toBe(1.0);
      expect(percentageToWeight(-50)).toBe(0.0);
    });
  });

  describe('Complex scenarios', () => {
    test('handles rapid successive updates', () => {
      let weights: SignalWeight[] = [
        { key: 'asr', weight: 0.33 },
        { key: 'image', weight: 0.33 },
        { key: 'metadata', weight: 0.34 }
      ];

      // Simulate user rapidly adjusting sliders
      weights = updateWeight(weights, 'asr', 0.5);
      expect(isNormalized(weights)).toBe(true);

      weights = updateWeight(weights, 'image', 0.3);
      expect(isNormalized(weights)).toBe(true);

      weights = updateWeight(weights, 'metadata', 0.1);
      expect(isNormalized(weights)).toBe(true);

      weights = updateWeight(weights, 'asr', 0.7);
      expect(isNormalized(weights)).toBe(true);
    });

    test('handles locking and unlocking during adjustments', () => {
      let weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4 },
        { key: 'image', weight: 0.4 },
        { key: 'metadata', weight: 0.2 }
      ];

      // Lock ASR
      weights[0].locked = true;
      weights = updateWeight(weights, 'image', 0.6);
      expect(isNormalized(weights)).toBe(true);
      expect(weights[0].weight).toBeCloseTo(0.4); // Stayed locked

      // Unlock ASR
      weights[0].locked = false;
      weights = updateWeight(weights, 'metadata', 0.3);
      expect(isNormalized(weights)).toBe(true);
      // Now ASR can adjust
    });

    test('handles all signals locked (edge case)', () => {
      const weights: SignalWeight[] = [
        { key: 'asr', weight: 0.4, locked: true },
        { key: 'image', weight: 0.4, locked: true },
        { key: 'metadata', weight: 0.2, locked: true }
      ];
      const normalized = normalizeWeights(weights);
      // Should return as-is since we can't adjust anything
      expect(normalized[0].weight).toBe(0.4);
      expect(normalized[1].weight).toBe(0.4);
      expect(normalized[2].weight).toBe(0.2);
    });

    test('maintains stability with floating point arithmetic', () => {
      let weights: SignalWeight[] = [
        { key: 'asr', weight: 1/3 },
        { key: 'image', weight: 1/3 },
        { key: 'metadata', weight: 1/3 }
      ];

      // Multiple operations shouldn't cause drift
      for (let i = 0; i < 10; i++) {
        weights = updateWeight(weights, 'asr', 0.4);
        weights = updateWeight(weights, 'asr', 1/3);
      }

      expect(isNormalized(weights)).toBe(true);
      const sum = getWeightsSum(weights);
      expect(Math.abs(sum - 1.0)).toBeLessThan(1e-6);
    });
  });
});
