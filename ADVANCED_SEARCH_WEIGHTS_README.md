# Advanced Search Weights Component

A production-ready React component for adjusting multi-signal search weights with automatic normalization.

## Overview

The `AdvancedSearchWeights` component provides an intuitive UI for users to tune how much each signal (transcript/ASR, visual/image, metadata, etc.) contributes to search results. The key constraint is that **all weights must always sum to exactly 1.0 (100%)**.

### Key Features

- ✅ **Auto-normalization**: Weights always sum to 1.0, guaranteed
- ✅ **Intuitive UX**: Adjust one slider, others balance automatically
- ✅ **Presets**: Quick configurations for common use cases
- ✅ **Lock signals**: Prevent specific weights from auto-adjusting
- ✅ **Accessible**: Full keyboard navigation and ARIA labels
- ✅ **TypeScript**: Strict typing throughout
- ✅ **Tested**: Comprehensive unit test coverage

## Installation

```bash
# Copy these files to your project:
- src/lib/normalizeWeights.ts
- src/components/AdvancedSearchWeights.tsx
- src/__tests__/normalizeWeights.test.ts (optional)
```

## Basic Usage

```tsx
import { useState } from 'react';
import AdvancedSearchWeights, {
  SignalConfig,
  WeightPreset
} from '@/components/AdvancedSearchWeights';
import { SignalWeight } from '@/lib/normalizeWeights';

function SearchPage() {
  // Define your signals
  const signals: SignalConfig[] = [
    {
      key: 'asr',
      label: 'Transcript (ASR)',
      description: 'Weight for spoken words and subtitles'
    },
    {
      key: 'image',
      label: 'Visual Analysis',
      description: 'Weight for visual content in frames'
    },
    {
      key: 'metadata',
      label: 'Metadata',
      description: 'Weight for titles, tags, descriptions'
    }
  ];

  // Define presets
  const presets: WeightPreset[] = [
    {
      id: 'balanced',
      label: 'Balanced',
      weights: { asr: 0.4, image: 0.4, metadata: 0.2 }
    },
    {
      id: 'dialogue',
      label: 'Dialogue-Heavy',
      weights: { asr: 0.7, image: 0.2, metadata: 0.1 }
    }
  ];

  // State for weights
  const [weights, setWeights] = useState<SignalWeight[]>([
    { key: 'asr', weight: 0.4 },
    { key: 'image', weight: 0.4 },
    { key: 'metadata', weight: 0.2 }
  ]);

  return (
    <AdvancedSearchWeights
      signals={signals}
      value={weights}
      onChange={setWeights}
      presets={presets}
      step={0.05}
    />
  );
}
```

## API Reference

### Component Props

#### `AdvancedSearchWeightsProps`

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `signals` | `SignalConfig[]` | Yes | - | Configuration for each signal |
| `value` | `SignalWeight[]` | Yes | - | Current weight values (controlled) |
| `onChange` | `(value: SignalWeight[]) => void` | Yes | - | Callback when weights change |
| `presets` | `WeightPreset[]` | No | `[]` | Preset configurations |
| `step` | `number` | No | `0.05` | Step size for slider (0.05 = 5%) |
| `showAdvanced` | `boolean` | No | `false` | Show lock buttons |

#### `SignalConfig`

```typescript
type SignalConfig = {
  key: SearchSignalKey;        // Unique identifier
  label: string;                // Display name
  description?: string;         // Tooltip/helper text
  color?: string;              // Tailwind color class
  min?: number;                // Min value (default: 0)
  max?: number;                // Max value (default: 1)
};
```

#### `SignalWeight`

```typescript
type SignalWeight = {
  key: SearchSignalKey;        // Matches SignalConfig.key
  weight: number;              // Value 0-1
  locked?: boolean;            // If true, won't auto-adjust
};
```

#### `WeightPreset`

```typescript
type WeightPreset = {
  id: string;                  // Unique preset ID
  label: string;               // Display name
  description?: string;        // Optional description
  weights: Record<SearchSignalKey, number>; // Must sum to 1
};
```

## Normalization Algorithm

The component uses a sophisticated normalization strategy to maintain the sum = 1.0 constraint:

### How It Works

1. **User adjusts a slider** to a new value
2. **Calculate delta**: difference from old value
3. **Distribute delta** proportionally across other **unlocked** signals
   - Signals with higher weights absorb more change
   - Locked signals remain unchanged
4. **Clamp values** to [0, 1] range
5. **Final normalization** pass to handle rounding errors

### Example

Starting weights: ASR=0.4, Image=0.4, Metadata=0.2

**User increases ASR to 0.6:**
- Delta = +0.2
- Remaining budget for others = 0.4
- Image had 0.4, Metadata had 0.2 (ratio 2:1)
- New Image = 0.4 × (0.4/0.6) ≈ 0.267
- New Metadata = 0.2 × (0.4/0.6) ≈ 0.133
- **Result: ASR=0.6, Image=0.267, Metadata=0.133** ✅ Sum=1.0

### Edge Cases Handled

- ✅ All weights at 0 → Distribute evenly
- ✅ Single weight at 1.0 → Others go to 0
- ✅ Locked signals exceed 1.0 → Scale down proportionally
- ✅ Floating-point precision → Epsilon tolerance (1e-6)
- ✅ All signals locked → Return as-is (no normalization possible)

## Utility Functions

The `normalizeWeights.ts` module exports these utilities:

```typescript
// Check if weights sum to 1.0
isNormalized(weights: SignalWeight[]): boolean

// Get current sum
getWeightsSum(weights: SignalWeight[]): number

// Normalize weights to sum to 1.0
normalizeWeights(weights: SignalWeight[]): SignalWeight[]

// Update single weight and auto-balance others
updateWeight(
  weights: SignalWeight[],
  targetKey: SearchSignalKey,
  newWeight: number
): SignalWeight[]

// Apply preset configuration
applyPreset(
  weights: SignalWeight[],
  preset: Record<SearchSignalKey, number>
): SignalWeight[]

// Round to step (e.g., 0.05 for 5% increments)
roundToStep(weight: number, step: number): number

// Convert weight (0-1) to percentage string
weightToPercentage(weight: number, decimals?: number): string

// Convert percentage (0-100) to weight (0-1)
percentageToWeight(percentage: number): number
```

## Integration with Search API

When integrating with your search backend:

```typescript
// In your search form component
const [searchQuery, setSearchQuery] = useState('');
const [weights, setWeights] = useState<SignalWeight[]>([...]);

const handleSearch = async () => {
  // Convert weights array to object
  const weightsObj = weights.reduce((acc, w) => {
    acc[w.key] = w.weight;
    return acc;
  }, {} as Record<string, number>);

  // Send to backend
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: searchQuery,
      weights: weightsObj  // { asr: 0.4, image: 0.4, metadata: 0.2 }
    })
  });

  const results = await response.json();
  // Handle results...
};
```

### Backend Example (FastAPI)

```python
from pydantic import BaseModel
from typing import Dict

class SearchRequest(BaseModel):
    query: str
    weights: Dict[str, float]  # { "asr": 0.4, "image": 0.4, "metadata": 0.2 }

@router.post("/search")
async def search(request: SearchRequest):
    # Validate weights sum to 1.0
    total = sum(request.weights.values())
    assert abs(total - 1.0) < 1e-6, "Weights must sum to 1.0"

    # Use weights in your search algorithm
    results = hybrid_search(
        query=request.query,
        asr_weight=request.weights.get("asr", 0),
        image_weight=request.weights.get("image", 0),
        metadata_weight=request.weights.get("metadata", 0)
    )

    return results
```

## Testing

Run the comprehensive test suite:

```bash
# Using Jest
npm test normalizeWeights.test.ts

# With coverage
npm test -- --coverage normalizeWeights.test.ts
```

### Test Coverage

The test suite covers:
- ✅ Normalization with various sums (>1, <1, =0)
- ✅ Single weight updates
- ✅ Locked signal behavior
- ✅ Preset application
- ✅ Edge cases (all locked, single signal, etc.)
- ✅ Floating-point stability
- ✅ Rapid successive updates
- ✅ Conversion utilities

## Demo Page

Visit the demo page to see the component in action:

```bash
npm run dev
# Navigate to http://localhost:3000/demo-weights
```

The demo page includes:
1. Basic usage example
2. Advanced mode with locks
3. Integration with search form
4. Usage guide and documentation

## Accessibility

The component is fully accessible:

- ✅ **Keyboard Navigation**: Tab through controls, use arrow keys on sliders
- ✅ **ARIA Labels**: All interactive elements properly labeled
- ✅ **Screen Reader Support**: Announces current values and changes
- ✅ **Focus Management**: Clear focus indicators
- ✅ **Semantic HTML**: Proper form controls and labels

## Styling

The component uses Tailwind CSS classes. To customize:

```tsx
// Override classes in your component
<AdvancedSearchWeights
  signals={signals}
  value={weights}
  onChange={setWeights}
  className="custom-styling" // Add your own
/>
```

Or modify the component source directly to match your design system.

## Common Use Cases

### 1. Video Search Platform

```typescript
const signals: SignalConfig[] = [
  { key: 'asr', label: 'Transcript', description: 'Spoken dialogue' },
  { key: 'visual', label: 'Visual', description: 'On-screen content' },
  { key: 'ocr', label: 'Text on Screen', description: 'Detected text' },
  { key: 'metadata', label: 'Metadata', description: 'Title, tags, etc.' }
];

const presets: WeightPreset[] = [
  {
    id: 'interview',
    label: 'Interview/Podcast',
    weights: { asr: 0.7, visual: 0.1, ocr: 0.1, metadata: 0.1 }
  },
  {
    id: 'presentation',
    label: 'Presentation',
    weights: { asr: 0.2, visual: 0.3, ocr: 0.4, metadata: 0.1 }
  }
];
```

### 2. Document Search

```typescript
const signals: SignalConfig[] = [
  { key: 'content', label: 'Content', description: 'Document body text' },
  { key: 'title', label: 'Title', description: 'Document title' },
  { key: 'author', label: 'Author', description: 'Author information' },
  { key: 'tags', label: 'Tags', description: 'User-defined tags' }
];
```

### 3. E-commerce Search

```typescript
const signals: SignalConfig[] = [
  { key: 'product_name', label: 'Product Name' },
  { key: 'description', label: 'Description' },
  { key: 'reviews', label: 'Customer Reviews' },
  { key: 'attributes', label: 'Attributes' }
];
```

## Troubleshooting

### Weights don't sum to exactly 1.0

Check the epsilon tolerance:
```typescript
import { isNormalized, getWeightsSum } from '@/lib/normalizeWeights';

if (!isNormalized(weights)) {
  console.log('Sum:', getWeightsSum(weights));
  // Should be within 1e-6 of 1.0
}
```

### Locked signals causing issues

Ensure locked signals don't exceed 1.0 total:
```typescript
const lockedSum = weights
  .filter(w => w.locked)
  .reduce((sum, w) => sum + w.weight, 0);

if (lockedSum > 1.0) {
  console.error('Locked signals exceed 100%');
}
```

### Slider not updating smoothly

Adjust the step size:
```tsx
<AdvancedSearchWeights
  step={0.01}  // Smaller steps = smoother
  // ...
/>
```

## Performance Considerations

- Component is **controlled**, so parent manages state
- Normalization runs on every weight change (~O(n) where n = number of signals)
- For 3-5 signals: negligible performance impact
- For 10+ signals: consider debouncing onChange callbacks
- Memoization not required unless rendering 100+ components

## Future Enhancements

Potential improvements:
- [ ] Drag-and-drop to reorder signals
- [ ] Visualization of weight distribution (pie chart)
- [ ] Undo/redo functionality
- [ ] Save custom presets to localStorage
- [ ] Animation when weights change
- [ ] Dark mode support
- [ ] Mobile touch gestures

## License

MIT - Feel free to use in your project!

## Contributing

Contributions welcome! Please:
1. Add tests for new features
2. Update documentation
3. Follow existing code style
4. Ensure all tests pass

## Support

For issues or questions:
- Check the demo page: `/demo-weights`
- Review the test suite for usage examples
- File an issue with reproduction steps

---

**Built with React, TypeScript, and Tailwind CSS**
