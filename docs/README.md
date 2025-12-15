# Heimdex Documentation

Welcome to the Heimdex documentation. This directory contains comprehensive guides and technical documentation for the Heimdex video search and scene analysis platform.

## Core Documentation

### [Search Pipeline](./search-pipeline.md)
**Complete end-to-end documentation of Heimdex search architecture**
- How hybrid search (dense vector + BM25 lexical + RRF fusion) works
- Indexing pipeline: video processing, scene detection, embedding generation
- Query pipeline: retrieval, ranking, and response flow
- OpenSearch and PostgreSQL (pgvector) integration details
- Edge cases, fallbacks, observability, and debugging guide
- Performance analysis and cost optimization strategies
- Code pointer index mapping every stage to source files

**Read this first** if you need to:
- Understand how search works in Heimdex
- Debug search quality or performance issues
- Add new search modalities (e.g., OCR)
- Modify ranking or fusion logic
- Optimize indexing costs or latency

---

## Feature Specifications

### [YouTube Shorts Export Feature](./FEATURE_SPEC_YOUTUBE_SHORTS_EXPORT.md)
Detailed specification for scene export functionality:
- Export individual scenes as vertical (9:16) short videos
- Aspect ratio handling strategies (crop, blur, pad)
- Quality presets and ffmpeg processing
- Rate limiting and temporary storage with expiration

### [YouTube Shorts Export Decisions](./YOUTUBE_SHORTS_EXPORT_DECISIONS.md)
Key architectural decisions for the export feature:
- Worker-based asynchronous processing
- Temporary storage with auto-expiry
- Rate limiting strategy
- Database schema design

---

## Implementation Summaries

### [Phase 1: Core Video Processing](./PHASE1_IMPLEMENTATION_SUMMARY.md)
- Video upload and storage (Supabase)
- Scene detection (PySceneDetect)
- Audio transcription (Whisper)
- Basic visual analysis (GPT-4o Vision)

### [Phase 2: Advanced Semantics](./PHASE2_IMPLEMENTATION_SUMMARY.md)
- Enhanced visual analysis with entities and actions
- Cost-optimized processing rules
- Sidecar v2 with versioning
- Video-level summaries

### [Phase 3: Hybrid Search](./PHASE3_IMPLEMENTATION_SUMMARY.md)
- OpenSearch integration for BM25 lexical search
- Korean/English multi-field analyzers (nori plugin)
- Reciprocal Rank Fusion (RRF)
- Fallback modes and graceful degradation

---

## Architecture and Development

### [Architecture Overview](./ARCHITECTURE_OVERVIEW.md)
High-level system architecture:
- Microservices structure (Frontend, API, Worker)
- Technology stack
- Service boundaries and communication
- Deployment architecture (Railway)

### [Development Log](./DEVLOG.md)
Historical development notes and decisions

---

## Search Subsystem Documentation

### [OpenSearch Analyzers](./search/opensearch-analyzers.md)
Detailed guide for Korean/English analyzer setup:
- Index mapping with multi-field strategy
- Nori plugin installation and configuration
- Deployment steps for local and Railway
- Troubleshooting guide

**Note:** This is supplementary to the main [Search Pipeline](./search-pipeline.md) documentation

---

## Quick Navigation by Use Case

**I want to...**

- **Understand how search works** → [Search Pipeline](./search-pipeline.md)
- **Debug search results** → [Search Pipeline: Observability & Debugging](./search-pipeline.md#observability--debugging)
- **Optimize search performance** → [Search Pipeline: Performance & Unit Economics](./search-pipeline.md#performance--unit-economics)
- **Add a new video processing feature** → [Phase 1](./PHASE1_IMPLEMENTATION_SUMMARY.md) + [Architecture Overview](./ARCHITECTURE_OVERVIEW.md)
- **Modify scene export** → [YouTube Shorts Export Feature](./FEATURE_SPEC_YOUTUBE_SHORTS_EXPORT.md)
- **Deploy to production** → [Search Pipeline: Edge Cases](./search-pipeline.md#edge-cases--fallbacks) + [OpenSearch Analyzers](./search/opensearch-analyzers.md)
- **Understand cost structure** → [Search Pipeline: Unit Economics](./search-pipeline.md#performance--unit-economics)

---

## Contributing to Documentation

When adding new documentation:

1. Place technical guides in `/docs/` root
2. Place subsystem-specific docs in `/docs/<subsystem>/`
3. Update this README with a link and description
4. Include code pointers (file paths and line numbers)
5. Add Mermaid diagrams where helpful
6. Document edge cases and failure modes

---

**Last Updated:** 2025-12-15
