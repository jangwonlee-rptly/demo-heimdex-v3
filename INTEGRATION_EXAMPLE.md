# Integrating Advanced Search Weights with Heimdex

This guide shows how to integrate the `AdvancedSearchWeights` component with the existing Heimdex video search functionality.

## Architecture Overview

```
┌─────────────────┐
│  Search Page    │
│  (Frontend)     │
│                 │
│  ┌───────────┐  │
│  │  Query    │  │
│  │  Input    │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │  Weights  │  │
│  │  Component│  │
│  └───────────┘  │
└────────┬────────┘
         │ POST /search
         ↓
┌─────────────────┐
│  FastAPI        │
│  Backend        │
│                 │
│  weights: {     │
│    asr: 0.4,    │
│    image: 0.4,  │
│    metadata:0.2 │
│  }              │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Hybrid Search  │
│  Algorithm      │
│                 │
│  weighted_sum(  │
│    asr_score,   │
│    image_score, │
│    meta_score   │
│  )              │
└─────────────────┘
```

## Step 1: Update Search Request Schema

### Backend (`services/api/src/domain/schemas.py`)

Add weights to the search request:

```python
from typing import Optional, Dict
from pydantic import BaseModel, Field, field_validator

class SearchRequest(BaseModel):
    """Search request with multi-signal weights."""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")
    threshold: float = Field(0.2, ge=0.0, le=1.0, description="Similarity threshold")
    video_id: Optional[str] = Field(None, description="Optional video filter")

    # New: Signal weights
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Signal weights (must sum to 1.0)"
    )

    @field_validator('weights')
    @classmethod
    def validate_weights(cls, v):
        """Ensure weights sum to 1.0 within epsilon."""
        if v is not None:
            total = sum(v.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v

    @property
    def asr_weight(self) -> float:
        """Get ASR weight with fallback to default."""
        return self.weights.get('asr', 0.4) if self.weights else 0.4

    @property
    def image_weight(self) -> float:
        """Get image weight with fallback to default."""
        return self.weights.get('image', 0.4) if self.weights else 0.4

    @property
    def metadata_weight(self) -> float:
        """Get metadata weight with fallback to default."""
        return self.weights.get('metadata', 0.2) if self.weights else 0.2
```

## Step 2: Update Search Endpoint

### Backend (`services/api/src/routes/search.py`)

Modify the search endpoint to use weights:

```python
@router.post("/search", response_model=SearchResponse)
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search for video scenes using natural language with weighted signals.
    """
    user_id = UUID(current_user.user_id)

    logger.info(
        f"Search request: query='{request.query}', "
        f"weights={request.weights or 'default'}"
    )

    # Generate embedding for query (this is the "asr" component)
    query_embedding = openai_client.create_embedding(request.query)

    # Search with weights
    scenes = db.search_scenes_weighted(
        query_embedding=query_embedding,
        limit=request.limit,
        threshold=request.threshold,
        video_id=request.video_id,
        user_id=user_id,
        # Pass weights to database function
        asr_weight=request.asr_weight,
        image_weight=request.image_weight,
        metadata_weight=request.metadata_weight,
    )

    return SearchResponse(
        query=request.query,
        results=[...],
        total=len(scenes),
        latency_ms=int((time.time() - start_time) * 1000)
    )
```

## Step 3: Update Database Search Function

### Backend (`services/api/src/adapters/database.py`)

Update the search function to apply weights:

```python
def search_scenes_weighted(
    self,
    query_embedding: List[float],
    limit: int = 20,
    threshold: float = 0.2,
    video_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    asr_weight: float = 0.4,
    image_weight: float = 0.4,
    metadata_weight: float = 0.2,
) -> List[VideoScene]:
    """
    Search scenes with weighted multi-signal scoring.

    For now, we primarily use the combined embedding which already includes
    ASR + visual + metadata. In the future, you could:
    1. Store separate embeddings for each signal
    2. Compute weighted similarity across all embeddings
    3. Combine scores using the provided weights

    Current implementation:
    - Use existing combined embedding
    - Apply weights as multipliers in future iterations
    """
    # Build query
    query = """
        SELECT
            vs.id,
            vs.video_id,
            vs.index,
            vs.start_s,
            vs.end_s,
            vs.transcript_segment,
            vs.visual_summary,
            vs.combined_text,
            vs.thumbnail_url,
            vs.visual_description,
            vs.visual_entities,
            vs.visual_actions,
            vs.tags,
            vs.created_at,
            -- Cosine similarity
            (1 - (vs.embedding <=> %s::vector)) as similarity
        FROM video_scenes vs
        JOIN videos v ON v.id = vs.video_id
        WHERE
            v.owner_id = %s
            AND v.status = 'READY'
            {video_filter}
            AND (1 - (vs.embedding <=> %s::vector)) >= %s
        ORDER BY similarity DESC
        LIMIT %s
    """

    # Apply video filter if specified
    video_filter = "AND v.id = %s" if video_id else ""
    query = query.format(video_filter=video_filter)

    # Build parameters
    params = [
        query_embedding,  # First embedding comparison
        str(user_id),
        query_embedding,  # Second embedding comparison
        threshold,
    ]

    if video_id:
        params.insert(3, str(video_id))  # Insert after user_id

    params.append(limit)

    # Execute query
    with self.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    # Convert to VideoScene objects
    return [VideoScene(**row) for row in rows]
```

### Future Enhancement: Multi-Embedding Search

For true multi-signal search, you would:

1. **Store separate embeddings** for each signal:
```sql
ALTER TABLE video_scenes
ADD COLUMN asr_embedding vector(1536),
ADD COLUMN image_embedding vector(1536),
ADD COLUMN metadata_embedding vector(1536);
```

2. **Compute weighted similarity**:
```python
def search_scenes_weighted(
    self,
    query_embedding: List[float],
    asr_weight: float = 0.4,
    image_weight: float = 0.4,
    metadata_weight: float = 0.2,
    # ... other params
) -> List[VideoScene]:
    """Search with true multi-signal weighting."""
    query = """
        SELECT
            vs.*,
            -- Weighted similarity across all signals
            (
                %s * (1 - (vs.asr_embedding <=> %s::vector)) +
                %s * (1 - (vs.image_embedding <=> %s::vector)) +
                %s * (1 - (vs.metadata_embedding <=> %s::vector))
            ) as weighted_similarity
        FROM video_scenes vs
        JOIN videos v ON v.id = vs.video_id
        WHERE v.owner_id = %s AND v.status = 'READY'
        ORDER BY weighted_similarity DESC
        LIMIT %s
    """

    params = [
        asr_weight, query_embedding,
        image_weight, query_embedding,
        metadata_weight, query_embedding,
        str(user_id),
        limit
    ]

    # ... execute query
```

## Step 4: Update Frontend Search Page

### Frontend (`services/frontend/src/app/search/page.tsx`)

Integrate the weights component:

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import AdvancedSearchWeights, {
  SignalConfig,
  WeightPreset
} from '@/components/AdvancedSearchWeights';
import { SignalWeight } from '@/lib/normalizeWeights';
import type { SearchResult } from '@/types';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Signal configurations
  const signals: SignalConfig[] = [
    {
      key: 'asr',
      label: 'Transcript',
      description: 'Weight for spoken words and audio transcription'
    },
    {
      key: 'image',
      label: 'Visual',
      description: 'Weight for visual content in video frames'
    },
    {
      key: 'metadata',
      label: 'Metadata',
      description: 'Weight for titles, tags, and descriptions'
    }
  ];

  // Presets
  const presets: WeightPreset[] = [
    {
      id: 'balanced',
      label: 'Balanced',
      description: 'Equal weight for all signals',
      weights: { asr: 0.4, image: 0.4, metadata: 0.2 }
    },
    {
      id: 'dialogue',
      label: 'Dialogue-Heavy',
      description: 'For interviews, podcasts, meetings',
      weights: { asr: 0.7, image: 0.2, metadata: 0.1 }
    },
    {
      id: 'visual',
      label: 'Visual-Heavy',
      description: 'For presentations, visual content',
      weights: { asr: 0.1, image: 0.7, metadata: 0.2 }
    }
  ];

  // Weights state
  const [weights, setWeights] = useState<SignalWeight[]>([
    { key: 'asr', weight: 0.4 },
    { key: 'image', weight: 0.4 },
    { key: 'metadata', weight: 0.2 }
  ]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);

    try {
      // Convert weights array to object
      const weightsObj = weights.reduce((acc, w) => {
        acc[w.key] = w.weight;
        return acc;
      }, {} as Record<string, number>);

      // Send search request with weights
      const searchResults = await apiRequest<SearchResult>('/search', {
        method: 'POST',
        body: JSON.stringify({
          query: query.trim(),
          limit: 20,
          threshold: 0.2,
          weights: weightsObj  // ← Include weights
        }),
      });

      setResults(searchResults);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Search Form */}
        <div className="card mb-6">
          <h1 className="text-2xl font-bold mb-4">Semantic Search</h1>

          <form onSubmit={handleSearch} className="space-y-4">
            {/* Search Input */}
            <div className="flex gap-4">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search for scenes..."
                className="input flex-1"
              />
              <button
                type="submit"
                disabled={searching || !query.trim()}
                className="btn btn-primary"
              >
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>

            {/* Advanced Toggle */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              {showAdvanced ? '▼' : '▶'} Advanced: Adjust Signal Weights
            </button>

            {/* Advanced Weights */}
            {showAdvanced && (
              <div className="pt-4">
                <AdvancedSearchWeights
                  signals={signals}
                  value={weights}
                  onChange={setWeights}
                  presets={presets}
                  step={0.05}
                  showAdvanced={false}
                />
              </div>
            )}
          </form>

          {/* Results Summary */}
          {results && (
            <div className="mt-4 text-sm text-gray-600">
              Found {results.total} results in {results.latency_ms}ms
              {showAdvanced && (
                <span className="ml-2">
                  (Weights: ASR {Math.round(weights[0].weight * 100)}%,
                   Visual {Math.round(weights[1].weight * 100)}%,
                   Metadata {Math.round(weights[2].weight * 100)}%)
                </span>
              )}
            </div>
          )}
        </div>

        {/* Search Results */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ... existing results display ... */}
        </div>
      </div>
    </div>
  );
}
```

## Step 5: Test the Integration

### 1. Start the services:

```bash
docker-compose up --build
```

### 2. Navigate to search page:

```
http://localhost:3000/search
```

### 3. Test different scenarios:

**Scenario A: Dialogue-heavy content**
- Query: "person talking about machine learning"
- Preset: "Dialogue-Heavy" (ASR 70%)
- Should prioritize transcript matches

**Scenario B: Visual content**
- Query: "person presenting slides"
- Preset: "Visual-Heavy" (Image 70%)
- Should prioritize visual matches

**Scenario C: Custom weights**
- Query: "technical presentation"
- Manually adjust: ASR 30%, Visual 50%, Metadata 20%
- See how results change

## Step 6: Monitor and Iterate

### Add analytics to track weight usage:

```python
# In search endpoint
db.log_search_query(
    user_id=user_id,
    query_text=request.query,
    results_count=len(scenes),
    latency_ms=latency_ms,
    video_id=request.video_id,
    # NEW: Log weights used
    metadata={
        "weights": request.weights or "default",
        "asr_weight": request.asr_weight,
        "image_weight": request.image_weight,
        "metadata_weight": request.metadata_weight
    }
)
```

### Analyze what weights users prefer:

```sql
SELECT
    metadata->>'weights' as weights_used,
    COUNT(*) as search_count,
    AVG(results_count) as avg_results
FROM search_queries
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY metadata->>'weights'
ORDER BY search_count DESC;
```

## Future Enhancements

1. **A/B Testing**: Test different default weights
2. **Personalization**: Learn user preferences over time
3. **Auto-tuning**: Suggest weights based on query type
4. **Explain Results**: Show which signal contributed most to each result
5. **Signal Quality Scores**: Weight by confidence in each signal

## Troubleshooting

### Weights not affecting results

Check that:
1. Backend is receiving weights: Add logging in search endpoint
2. Database query uses weights: Verify SQL query
3. Multiple embeddings exist: For true multi-signal search

### Performance issues

If search is slow with weights:
1. Add indexes for each embedding column
2. Use approximate nearest neighbor (HNSW)
3. Cache frequent queries
4. Consider pre-computing weighted embeddings

## Summary

You now have:
- ✅ Frontend component for weight adjustment
- ✅ Backend validation and processing
- ✅ Database integration (placeholder for multi-signal)
- ✅ Analytics and monitoring
- ✅ Testing and iteration framework

The weights component is ready to use and can evolve as your multi-signal search capabilities grow!
