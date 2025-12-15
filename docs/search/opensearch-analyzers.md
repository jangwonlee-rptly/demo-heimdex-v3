# OpenSearch Korean/English Multi-Field Analyzers

## Overview

This document describes the Korean and English language-aware BM25 search implementation in Heimdex using OpenSearch multi-field analyzers.

**Last updated:** 2025-12-15

## What Changed

### 1. OpenSearch Index Mapping

The scene index (`scene_docs`) now uses **multi-field mapping** for better Korean and English lexical retrieval:

- **Base field** (`standard` analyzer): Keeps existing behavior for backward compatibility
- **Korean subfield** (`.ko`): Uses `nori_tokenizer` for proper Korean morphological analysis
- **English subfield** (`.en`): Uses `english` analyzer with stemming and stop words

**Affected fields:**
- `transcript_segment`
- `visual_summary`
- `visual_description`
- `combined_text`
- `tags_text`

### 2. Custom Analyzers

Two custom analyzers are defined in the index settings:

```json
{
  "ko_nori": {
    "type": "custom",
    "tokenizer": "nori_tokenizer",
    "filter": ["lowercase"]
  },
  "en_english": {
    "type": "english"
  }
}
```

### 3. BM25 Query Update

The BM25 search query now searches **all three variants** of each field:
- `field_name` (standard analyzer)
- `field_name.ko` (Korean nori analyzer)
- `field_name.en` (English analyzer)

**Example:** A query for "사람" (person in Korean) will now properly tokenize and match Korean text using morphological analysis.

### 4. Nori Plugin Installation

The OpenSearch Docker image now includes the `analysis-nori` plugin, installed at build time.

## Prerequisites

- OpenSearch 2.x
- `analysis-nori` plugin (auto-installed via custom Dockerfile)

## How to Use

### Local Development

#### 1. Rebuild OpenSearch with nori plugin

```bash
# From repo root
docker-compose down opensearch
docker-compose build opensearch
docker-compose up -d opensearch
```

Wait for OpenSearch to be healthy:

```bash
docker-compose ps opensearch
# Wait until status shows "healthy"
```

#### 2. Recreate the index

**IMPORTANT:** Changing analyzers requires recreating the index.

Option A: Delete and recreate (simplest for local dev):

```bash
# Delete existing index
curl -X DELETE http://localhost:9200/scene_docs

# Index will be auto-created with new mapping on next API/worker startup
docker-compose restart api worker
```

Option B: Use reindex script (safer for production):

```bash
# From worker container
docker-compose exec worker python -m src.scripts.reindex_opensearch --help
```

#### 3. Reindex existing scenes

```bash
# Dry run first to verify
docker-compose exec worker python -m src.scripts.reindex_opensearch --dry-run

# Run actual reindex
docker-compose exec worker python -m src.scripts.reindex_opensearch --batch-size 100 --sleep 0.2
```

**Parameters:**
- `--batch-size`: Number of scenes per batch (default: 100)
- `--sleep`: Seconds between batches to avoid overload (default: 0.2)
- `--video-id`: Only reindex specific video
- `--dry-run`: Preview without indexing

#### 4. Verify with smoke tests

```bash
# From API container
docker-compose exec api python -m src.scripts.smoke_hybrid_search --verbose

# Test with Korean query
docker-compose exec api python -m src.scripts.smoke_hybrid_search --query "사람" --owner-id <your-user-id>

# Test with English query
docker-compose exec api python -m src.scripts.smoke_hybrid_search --query "person walking" --owner-id <your-user-id>
```

### Railway Deployment

#### 1. Update Railway OpenSearch service

Railway must build the custom OpenSearch image with nori plugin.

**Option A: Use custom Dockerfile (recommended)**

If Railway allows building from a custom Dockerfile path:
- Configure service to build from `services/opensearch/Dockerfile`

**Option B: Manual plugin installation**

If Railway uses base image only:
- Use Railway's shell access to manually install plugin:
  ```bash
  /usr/share/opensearch/bin/opensearch-plugin install analysis-nori --batch
  ```
- Restart the service

#### 2. Recreate index in Railway

**WARNING:** This will cause temporary search downtime.

```bash
# SSH into Railway API or worker service
railway run bash

# Delete old index
curl -X DELETE http://<opensearch-internal-url>:9200/scene_docs

# Restart API to auto-create new index
# (Or manually trigger via init_opensearch.py script)
python -m src.scripts.init_opensearch
```

#### 3. Reindex scenes

```bash
# From Railway worker service
railway run bash
python -m src.scripts.reindex_opensearch --batch-size 50 --sleep 0.5

# Monitor progress
# Should show: "Total indexed: X, Total errors: 0"
```

#### 4. Verify deployment

```bash
# Check nori plugin
curl http://<opensearch-url>:9200/_nodes/plugins | grep nori

# Run smoke test
python -m src.scripts.smoke_hybrid_search --verbose
```

## Troubleshooting

### Plugin Not Found

**Symptom:** Logs show "Nori plugin not found"

**Fix:**
1. Verify plugin installation:
   ```bash
   curl http://localhost:9200/_nodes/plugins
   ```
2. Rebuild OpenSearch image:
   ```bash
   docker-compose build --no-cache opensearch
   docker-compose up -d opensearch
   ```

### Index Already Exists Error

**Symptom:** "resource_already_exists_exception" when creating index

**Fix:**
- Delete the old index first: `curl -X DELETE http://localhost:9200/scene_docs`
- Or ignore (the code handles this gracefully)

### Mapping Conflict

**Symptom:** "mapper_parsing_exception" or "illegal_argument_exception" about analyzers

**Fix:**
- You cannot change analyzers on existing index
- Must recreate index (see step 2 above)

### Reindex Shows Zero Documents

**Check:**
1. Database has scenes: `SELECT COUNT(*) FROM video_scenes;`
2. Scenes have owner via video: `SELECT COUNT(*) FROM video_scenes vs JOIN videos v ON vs.video_id = v.id;`
3. OpenSearch indexing enabled: Check `OPENSEARCH_INDEXING_ENABLED` env var

### Korean Queries Return No Results

**Debugging:**
1. Check if nori plugin is installed (see above)
2. Test analyzer directly:
   ```bash
   curl -X POST "http://localhost:9200/scene_docs/_analyze" -H 'Content-Type: application/json' -d'
   {
     "analyzer": "ko_nori",
     "text": "사람이 걷고 있다"
   }
   '
   ```
   Should return tokenized Korean terms.
3. Verify data is indexed:
   ```bash
   curl -X GET "http://localhost:9200/scene_docs/_search?size=1&q=*"
   ```

## Performance Notes

- Multi-field mapping increases index size by ~30-40% (3 variants per field)
- Query latency increase: ~10-20ms (searches 3x fields)
- BM25 scoring: Each subfield scored independently; best score wins (type: `best_fields`)

## Rollback

If issues arise, rollback to previous mapping:

1. Revert code changes in:
   - `services/api/src/adapters/opensearch_client.py`
   - `services/worker/src/adapters/opensearch_client.py`
2. Delete index: `curl -X DELETE http://localhost:9200/scene_docs`
3. Restart services to recreate with old mapping
4. Reindex

## Future Improvements

- Consider SPLADE learned sparse retrieval (Step 2)
- Add language detection to route queries to appropriate subfield
- Tune BM25 parameters (k1, b) per language
- Add Japanese/Chinese analyzers if needed

## References

- [OpenSearch Nori Analysis Plugin](https://opensearch.org/docs/latest/analyzers/language-analyzers/#korean)
- [Multi-field Mapping](https://opensearch.org/docs/latest/field-types/mapping/)
- [BM25 Scoring](https://opensearch.org/docs/latest/query-dsl/full-text/match/)
