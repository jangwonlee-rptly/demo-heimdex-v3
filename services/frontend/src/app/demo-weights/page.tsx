'use client';

import { useState } from 'react';
import AdvancedSearchWeights, {
  SignalConfig,
  WeightPreset
} from '@/components/AdvancedSearchWeights';
import { SignalWeight } from '@/lib/normalizeWeights';

/**
 * Demo page for the AdvancedSearchWeights component.
 *
 * Shows different configurations and use cases.
 */
export default function DemoWeightsPage() {
  // Signal configurations
  const signals: SignalConfig[] = [
    {
      key: 'asr',
      label: 'Transcript (ASR)',
      description: 'Weight for spoken words and subtitles from audio transcription',
      color: 'blue'
    },
    {
      key: 'image',
      label: 'Visual Analysis',
      description: 'Weight for visual content detected in video frames',
      color: 'purple'
    },
    {
      key: 'metadata',
      label: 'Metadata',
      description: 'Weight for titles, descriptions, tags, and other metadata',
      color: 'green'
    }
  ];

  // Preset configurations
  const presets: WeightPreset[] = [
    {
      id: 'balanced',
      label: 'Balanced',
      description: 'Equal weight across all signals',
      weights: {
        asr: 0.4,
        image: 0.4,
        metadata: 0.2
      }
    },
    {
      id: 'dialogue',
      label: 'Dialogue-Heavy',
      description: 'Prioritize spoken content (interviews, podcasts)',
      weights: {
        asr: 0.7,
        image: 0.2,
        metadata: 0.1
      }
    },
    {
      id: 'visual',
      label: 'Visual-Heavy',
      description: 'Prioritize visual content (silent films, presentations)',
      weights: {
        asr: 0.1,
        image: 0.7,
        metadata: 0.2
      }
    },
    {
      id: 'metadata',
      label: 'Metadata-Heavy',
      description: 'Prioritize curated metadata (catalogued archives)',
      weights: {
        asr: 0.2,
        image: 0.2,
        metadata: 0.6
      }
    }
  ];

  // State for basic example
  const [basicWeights, setBasicWeights] = useState<SignalWeight[]>([
    { key: 'asr', weight: 0.4 },
    { key: 'image', weight: 0.4 },
    { key: 'metadata', weight: 0.2 }
  ]);

  // State for advanced example (with locks)
  const [advancedWeights, setAdvancedWeights] = useState<SignalWeight[]>([
    { key: 'asr', weight: 0.4, locked: false },
    { key: 'image', weight: 0.4, locked: false },
    { key: 'metadata', weight: 0.2, locked: false }
  ]);

  // State for search query
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<string | null>(null);

  // Simulate search
  const handleSearch = () => {
    const weightsObj = basicWeights.reduce((acc, w) => {
      acc[w.key] = w.weight;
      return acc;
    }, {} as Record<string, number>);

    const payload = {
      query: searchQuery,
      weights: weightsObj
    };

    setSearchResults(JSON.stringify(payload, null, 2));
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Advanced Search Weights Demo
          </h1>
          <p className="text-lg text-gray-600 max-w-3xl mx-auto">
            Interactive demonstration of the weight adjustment component for multi-signal search.
            All weights automatically normalize to sum to 100%.
          </p>
        </div>

        {/* Example 1: Basic Usage */}
        <section className="space-y-4">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              1. Basic Usage
            </h2>
            <p className="text-gray-600 mb-4">
              Adjust sliders to see auto-normalization in action. Try moving any slider
              and watch the others adjust proportionally.
            </p>
          </div>
          <AdvancedSearchWeights
            signals={signals}
            value={basicWeights}
            onChange={setBasicWeights}
            presets={presets}
            step={0.05}
          />

          {/* Show current state */}
          <div className="bg-gray-900 text-white p-4 rounded-lg font-mono text-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Current State:</span>
              <span className="text-xs text-gray-500">JSON Output</span>
            </div>
            <pre className="overflow-x-auto">
              {JSON.stringify(
                basicWeights.reduce((acc, w) => {
                  acc[w.key] = Math.round(w.weight * 100) / 100;
                  return acc;
                }, {} as Record<string, number>),
                null,
                2
              )}
            </pre>
          </div>
        </section>

        {/* Example 2: Advanced with Locks */}
        <section className="space-y-4">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              2. Advanced Mode with Locks
            </h2>
            <p className="text-gray-600 mb-4">
              Lock signals to prevent them from auto-adjusting. Try locking the ASR weight
              and then adjusting the Image weight - only Metadata will compensate.
            </p>
          </div>
          <AdvancedSearchWeights
            signals={signals}
            value={advancedWeights}
            onChange={setAdvancedWeights}
            presets={presets}
            step={0.05}
            showAdvanced={true}
          />
        </section>

        {/* Example 3: Integration with Search */}
        <section className="space-y-4">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              3. Integration Example
            </h2>
            <p className="text-gray-600 mb-4">
              See how the weights integrate with a search form. The backend receives
              a clean, normalized payload.
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
            {/* Search Input */}
            <div>
              <label htmlFor="search-query" className="block text-sm font-medium text-gray-700 mb-2">
                Search Query
              </label>
              <div className="flex gap-2">
                <input
                  id="search-query"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g., person talking about AI"
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleSearch}
                  disabled={!searchQuery.trim()}
                  className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  Search
                </button>
              </div>
            </div>

            {/* Weights Component */}
            <AdvancedSearchWeights
              signals={signals}
              value={basicWeights}
              onChange={setBasicWeights}
              presets={presets}
              step={0.1}
            />

            {/* API Payload Preview */}
            {searchResults && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">
                  API Request Payload:
                </label>
                <div className="bg-gray-900 text-white p-4 rounded-lg font-mono text-sm">
                  <pre className="overflow-x-auto">{searchResults}</pre>
                </div>
                <p className="text-sm text-gray-600">
                  This payload would be sent to your search backend endpoint (e.g., POST /search)
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Documentation Section */}
        <section className="space-y-4">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">
              Usage Guide
            </h2>
            <div className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold text-lg mb-2">Key Features:</h3>
                <ul className="list-disc list-inside space-y-1 ml-4">
                  <li>Weights always sum to exactly 100% (1.0)</li>
                  <li>Adjust any slider and others auto-balance proportionally</li>
                  <li>Quick presets for common configurations</li>
                  <li>Lock individual signals to prevent auto-adjustment</li>
                  <li>Accessible keyboard navigation</li>
                  <li>Visual feedback for total weight validation</li>
                </ul>
              </div>

              <div>
                <h3 className="font-semibold text-lg mb-2">Component Props:</h3>
                <div className="bg-gray-50 p-4 rounded font-mono text-sm overflow-x-auto">
                  <pre>{`<AdvancedSearchWeights
  signals={[
    {
      key: 'asr',
      label: 'Transcript',
      description: 'Spoken words...'
    }
  ]}
  value={weights}
  onChange={setWeights}
  presets={presets}
  step={0.05}
  showAdvanced={true}
/>`}</pre>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-lg mb-2">Normalization Algorithm:</h3>
                <ol className="list-decimal list-inside space-y-1 ml-4">
                  <li>User adjusts a slider to a new value</li>
                  <li>Calculate the difference (delta) from old value</li>
                  <li>Distribute delta proportionally across unlocked signals</li>
                  <li>Signals with higher weights absorb more change</li>
                  <li>Clamp values between 0-1 and renormalize if needed</li>
                  <li>Final sum guaranteed to be 1.0 ± epsilon</li>
                </ol>
              </div>

              <div className="pt-4 border-t border-gray-200">
                <h3 className="font-semibold text-lg mb-2">Use Cases:</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <h4 className="font-medium mb-1">Dialogue-Heavy Content</h4>
                    <p className="text-sm">Interviews, podcasts, meetings - prioritize ASR</p>
                  </div>
                  <div className="p-4 bg-purple-50 rounded-lg">
                    <h4 className="font-medium mb-1">Visual-Heavy Content</h4>
                    <p className="text-sm">Silent films, presentations - prioritize visual</p>
                  </div>
                  <div className="p-4 bg-green-50 rounded-lg">
                    <h4 className="font-medium mb-1">Curated Archives</h4>
                    <p className="text-sm">Well-tagged libraries - prioritize metadata</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium mb-1">General Purpose</h4>
                    <p className="text-sm">Mixed content - use balanced weights</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <div className="text-center text-sm text-gray-500 py-8">
          <p>
            Advanced Search Weights Component • Built with React, TypeScript, and Tailwind CSS
          </p>
        </div>
      </div>
    </div>
  );
}
