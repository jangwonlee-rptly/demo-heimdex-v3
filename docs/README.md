# Heimdex Documentation

Welcome to the Heimdex documentation. This directory contains comprehensive guides and technical documentation for the Heimdex video search and scene analysis platform.

## Documentation Structure

```
docs/
├── architecture/       # System architecture and design
├── deployment/         # Deployment guides and checklists
├── features/          # Feature specifications and admin metrics
├── implementation/    # Phase summaries and migration guides
├── operations/        # Operations, backfill, and troubleshooting
├── search/           # Search pipeline documentation
└── testing/          # Testing guides and procedures
```

---

## Architecture

### [Architecture Overview](./architecture/OVERVIEW.md)
High-level system architecture:
- Microservices structure (Frontend, API, Worker)
- Technology stack
- Service boundaries and communication
- Deployment architecture (Railway)

### [Actor Architecture](./architecture/ACTOR_ARCHITECTURE.md)
Background worker (Dramatiq) architecture:
- Actor patterns and message passing
- Task queuing and job processing
- Retry strategies and error handling

---

## Deployment

### [Deployment Guide](./deployment/README.md)
**Complete deployment guide for production**:
- Platform comparison (Railway, Render, DigitalOcean, Fly.io)
- Step-by-step Railway deployment (recommended)
- Environment variable configuration
- Post-deployment verification
- Monitoring and maintenance
- Rollback strategies

### [Railway CLI Guide](./deployment/RAILWAY_CLI.md)
Command-line deployment using Railway CLI:
- Service creation and configuration
- Environment variable management
- Deployment and monitoring commands

### [Deployment Checklist](./deployment/CHECKLIST.md)
Pre-deployment, deployment, and post-deployment checklist:
- Local verification steps
- Supabase setup
- Service configuration
- Testing procedures
- Production hardening

### [CLIP RunPod Deployment](./deployment/CLIP_RUNPOD_DEPLOYMENT.md)
Complete guide for deploying CLIP inference to RunPod GPU:
- Docker image build and push
- RunPod endpoint configuration
- HMAC authentication setup
- Testing and verification
- Cost analysis

---

## Features

### [YouTube Shorts Export](./FEATURE_SPEC_YOUTUBE_SHORTS_EXPORT.md)
Specification for scene export functionality:
- Export individual scenes as vertical (9:16) short videos
- Aspect ratio handling strategies (crop, blur, pad)
- Quality presets and ffmpeg processing
- Rate limiting and temporary storage with expiration

### [YouTube Shorts Export Decisions](./YOUTUBE_SHORTS_EXPORT_DECISIONS.md)
Key architectural decisions:
- Worker-based asynchronous processing
- Temporary storage with auto-expiry
- Rate limiting strategy
- Database schema design

### [Admin Metrics Phase 1](./features/ADMIN_METRICS_PHASE1.md)
Initial admin dashboard metrics:
- Basic processing statistics
- Video count and status tracking
- User activity metrics

### [Admin Metrics Phase 2](./features/ADMIN_METRICS_PHASE2.md)
Advanced admin dashboard with performance metrics:
- Processing duration percentiles (p50/p95/p99)
- RTF (Real-Time Factor) calculation
- Queue vs run time separation
- Failure stage attribution
- Throughput calculation

---

## Implementation Summaries

### [Phase 1: Core Video Processing](./implementation/PHASE1_SUMMARY.md)
- Video upload and storage (Supabase)
- Scene detection (PySceneDetect)
- Audio transcription (Whisper)
- Basic visual analysis (GPT-4o Vision)

### [Phase 2: Advanced Semantics](./implementation/PHASE2_SUMMARY.md)
- Enhanced visual analysis with entities and actions
- Cost-optimized processing rules
- Sidecar v2 with versioning
- Video-level summaries

### [Phase 2 Deployment](./implementation/PHASE2_DEPLOYMENT_SUMMARY.md)
Deployment notes and migration guide for Phase 2 features

### [Phase 3: Hybrid Search](./implementation/PHASE3_SUMMARY.md)
- OpenSearch integration for BM25 lexical search
- Korean/English multi-field analyzers (nori plugin)
- Reciprocal Rank Fusion (RRF)
- Fallback modes and graceful degradation

### [CLIP RunPod Migration](./implementation/CLIP_RUNPOD_MIGRATION.md)
**Complete implementation summary for CLIP GPU migration**:
- Migration from local CPU to RunPod GPU (10-50x performance improvement)
- Architecture diagrams and file changes
- Environment variables and configuration
- Testing procedures and smoke tests
- Performance comparison and cost analysis
- Rollback plan and troubleshooting

---

## Operations

### [Backfill Quickstart](./operations/BACKFILL_QUICKSTART.md)
Quick guide for backfilling video processing timing data:
- When to run backfill
- Quick commands
- Verification steps

### [Docker Backfill Guide](./operations/DOCKER_BACKFILL_GUIDE.md)
Comprehensive guide for running backfill operations:
- Full procedure with Docker
- Environment setup
- Progress monitoring
- Troubleshooting

### [Thumbnail Troubleshooting](./operations/THUMBNAIL_TROUBLESHOOTING.md)
Common issues with thumbnail generation and solutions:
- Upload failures
- Missing thumbnails
- Quality issues
- Storage permissions

---

## Search Pipeline

### [Search Pipeline](./search-pipeline.md)
**Complete end-to-end documentation of Heimdex search architecture**:
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

### [Search Pipeline Deep Dive](./search-pipeline-deep-dive.md)
**Implementation-level deep dive** for senior engineers:
- Exhaustive scoring signal tables with weights and code pointers
- Timeout behavior per component (embedding, pgvector, OpenSearch)
- Cancellation and error handling semantics
- Risk analysis and cross-tenant isolation verification
- 10 prioritized improvements (quick wins to major refactors)
- Complete code pointer index (every function, every stage)

**Read this** if you need to:
- Understand exactly why a scene ranked above another
- Verify multi-tenant isolation is correctly enforced
- Plan search infrastructure improvements
- Onboard onto the search codebase quickly

### [OpenSearch Analyzers](./search/opensearch-analyzers.md)
Detailed guide for Korean/English analyzer setup:
- Index mapping with multi-field strategy
- Nori plugin installation and configuration
- Deployment steps for local and Railway
- Troubleshooting guide

### [Pipeline Report (2025-12-16)](./pipeline-report-20251216.md)
Historical pipeline analysis and optimization report

---

## Testing

### [Docker Testing Guide](./testing/DOCKER_TESTING.md)
Guide for testing the application using Docker:
- Local testing procedures
- Test data preparation
- Verification steps
- Common testing scenarios

---

## Development

### [Development Log](./DEVLOG.md)
Historical development notes and decisions

---

## Quick Navigation by Use Case

**I want to...**

- **Deploy to production** → [Deployment Guide](./deployment/README.md)
- **Understand the architecture** → [Architecture Overview](./architecture/OVERVIEW.md)
- **Understand how search works** → [Search Pipeline](./search-pipeline.md)
- **Debug search results** → [Search Pipeline: Observability & Debugging](./search-pipeline.md#observability--debugging)
- **Understand why Scene A ranked above Scene B** → [Deep Dive: Scoring Signals](./search-pipeline-deep-dive.md#scoring-signal-table)
- **Optimize search performance** → [Search Pipeline: Performance & Unit Economics](./search-pipeline.md#performance--unit-economics)
- **Plan search improvements** → [Deep Dive: Gaps & Improvements](./search-pipeline-deep-dive.md#gaps-risks-and-improvement-opportunities)
- **Add a new video processing feature** → [Phase 1 Summary](./implementation/PHASE1_SUMMARY.md) + [Architecture Overview](./architecture/OVERVIEW.md)
- **Modify scene export** → [YouTube Shorts Export Feature](./FEATURE_SPEC_YOUTUBE_SHORTS_EXPORT.md)
- **Set up admin dashboard metrics** → [Admin Metrics Phase 2](./features/ADMIN_METRICS_PHASE2.md)
- **Deploy CLIP to GPU** → [CLIP RunPod Deployment](./deployment/CLIP_RUNPOD_DEPLOYMENT.md)
- **Run backfill operations** → [Backfill Quickstart](./operations/BACKFILL_QUICKSTART.md)
- **Troubleshoot thumbnails** → [Thumbnail Troubleshooting](./operations/THUMBNAIL_TROUBLESHOOTING.md)
- **Understand cost structure** → [Search Pipeline: Unit Economics](./search-pipeline.md#performance--unit-economics)
- **Find a specific function** → [Deep Dive: Code Pointer Index](./search-pipeline-deep-dive.md#appendix-code-pointer-index-exhaustive)

---

## Contributing to Documentation

When adding new documentation:

1. **Choose the right directory**:
   - `architecture/` - System design and architecture
   - `deployment/` - Deployment guides and procedures
   - `features/` - Feature specifications
   - `implementation/` - Implementation summaries and migrations
   - `operations/` - Operational guides and troubleshooting
   - `search/` - Search-specific documentation
   - `testing/` - Testing guides

2. **Update this README** with a link and description
3. **Include code pointers** (file paths and line numbers)
4. **Add diagrams** (Mermaid format) where helpful
5. **Document edge cases** and failure modes
6. **Keep it current** - update when code changes

---

**Last Updated:** 2025-12-24
