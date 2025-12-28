# Heimdex - Vector Native Video Archive

A production-ready demo application that enables semantic search across videos using scene detection, AI-powered transcription, and vector embeddings.

## Features

- **User Authentication**: Signup/login with Supabase Auth
- **User Onboarding**: First-time user profile setup with marketing consent tracking
- **Video Upload**: Upload videos to Supabase Storage with progress tracking
- **Automated Processing**: Background worker processes videos into searchable scenes
- **Real-time Updates**: Dashboard automatically updates when video processing completes
- **Scene Detection**: Automatic scene boundary detection using PySceneDetect
- **AI Transcription**: Speech-to-text using OpenAI Whisper
- **Visual Analysis**: GPT-4o analyzes keyframes for visual context
- **Semantic Search**: Natural language search powered by OpenAI embeddings and pgvector
- **Query Logging**: All searches tracked with metadata and latency metrics
- **Scene Playback**: Jump directly to relevant scenes in the video player

## Architecture

```
┌─────────────┐
│   Frontend  │ Next.js 14 + TypeScript + Tailwind
│  (Port 3000)│
└──────┬──────┘
       │
       ↓
┌─────────────┐     ┌─────────────┐
│     API     │────→│   Worker    │
│  (Port 8000)│     │  (Dramatiq) │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ↓                   ↓
┌─────────────────────────────────┐
│          Supabase               │
│  ┌──────────┬──────────┬──────┐│
│  │ Postgres │ Storage  │ Auth ││
│  │+pgvector │          │      ││
│  └──────────┴──────────┴──────┘│
└─────────────────────────────────┘
       ↑                   ↑
       │                   │
┌──────┴──────┐     ┌──────┴──────┐
│    Redis    │     │   OpenAI    │
│  (Broker)   │     │     API     │
└─────────────┘     └─────────────┘
```

### Services

1. **Frontend** (`services/frontend/`)
   - Next.js 14 with App Router
   - Supabase client for auth
   - Video upload, search, and playback UI

2. **API** (`services/api/`)
   - FastAPI backend
   - JWT authentication middleware
   - REST endpoints for profiles, videos, and search
   - Enqueues background jobs

3. **Worker** (`services/worker/`)
   - Dramatiq background worker
   - Video processing pipeline
   - Scene detection, transcription, embedding generation

4. **Database**
   - Supabase Postgres with pgvector
   - Tables: `user_profiles`, `videos`, `video_scenes`, `search_queries`

5. **Queue**
   - Redis message broker for Dramatiq

## Prerequisites

- Docker & Docker Compose
- Supabase account (free tier works)
- OpenAI API key
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

## Quick Start

### 1. Set up Supabase

1. Create a new Supabase project at https://supabase.com
2. Go to Project Settings → API to get:
   - Project URL (`SUPABASE_URL`)
   - `anon` public key (`SUPABASE_ANON_KEY`)
   - `service_role` secret key (`SUPABASE_SERVICE_ROLE_KEY`)
3. Go to Project Settings → Database to get:
   - Connection string (`DATABASE_URL`)
4. Go to Project Settings → API → JWT Settings to get:
   - JWT Secret (`SUPABASE_JWT_SECRET`)

### 2. Run Database Migrations

Execute the SQL migrations in order in the Supabase SQL Editor:

1. `infra/migrations/001_initial_schema.sql`
2. `infra/migrations/002_enable_pgvector.sql`
3. `infra/migrations/003_create_indexes.sql`
4. `infra/migrations/004_add_filename_column.sql`
5. `infra/migrations/005_add_preferred_language.sql`
6. `infra/migrations/006_add_transcript_cache.sql`
7. `infra/migrations/007_add_user_filter_to_search.sql`
8. `infra/migrations/008_enable_realtime.sql` - **Required for real-time dashboard updates**

### 3. Create Storage Bucket

In Supabase Dashboard → Storage:

1. Create a new **public** bucket named `videos`
2. Set policies to allow authenticated users to upload

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbG...
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...
SUPABASE_JWT_SECRET=your-jwt-secret
DATABASE_URL=postgresql://postgres:[password]@db.xxxxx.supabase.co:5432/postgres
OPENAI_API_KEY=sk-...
```

### 5. Start Services

```bash
docker-compose up --build
```

This will start:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Worker: background service
- Redis: port 6379

### 6. Use the Application

1. Navigate to http://localhost:3000
2. Sign up for a new account
3. Complete the onboarding form
4. Upload a short video (< 100MB recommended for demo)
5. Wait for processing (check dashboard for status)
6. Search for scenes using natural language
7. Click results to jump to scenes in the video player

## Development

### API Service

```bash
cd services/api
uv sync
uv run uvicorn src.main:app --reload --port 8000
```

### Worker Service

```bash
cd services/worker
uv sync
uv run dramatiq src.tasks -p 1 -t 1
```

### Frontend

```bash
cd services/frontend
npm install
npm run dev
```

## Project Structure

```
demo-heimdex-v3/
├── services/
│   ├── api/                    # FastAPI backend
│   │   ├── src/
│   │   │   ├── auth/           # JWT middleware
│   │   │   ├── domain/         # Models & schemas
│   │   │   ├── adapters/       # External services
│   │   │   ├── routes/         # API endpoints
│   │   │   └── main.py         # App entry point
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── worker/                 # Dramatiq worker
│   │   ├── src/
│   │   │   ├── domain/         # Processing logic
│   │   │   ├── adapters/       # OpenAI, Supabase, FFmpeg
│   │   │   ├── tasks.py        # Dramatiq actors
│   │   │   └── config.py
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── frontend/               # Next.js UI
│       ├── src/
│       │   ├── app/            # Pages (App Router)
│       │   ├── components/     # React components
│       │   ├── lib/            # Supabase client
│       │   └── types/          # TypeScript types
│       ├── package.json
│       └── Dockerfile
├── infra/
│   └── migrations/             # SQL migrations
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

### Health
- `GET /health` - Health check

### Profile
- `GET /me` - Get user info from JWT
- `GET /me/profile` - Get user profile (null if not set)
- `POST /me/profile` - Create/update profile

### Videos
- `POST /videos/upload-url` - Get signed upload URL
- `POST /videos/{id}/uploaded` - Mark video uploaded, trigger processing
- `GET /videos` - List user's videos
- `GET /videos/{id}` - Get video details

### Search
- `POST /search` - Semantic scene search

## Database Schema

### `user_profiles`
User profile information collected during onboarding.

### `videos`
Video metadata and processing status.

### `video_scenes`
Scene-level sidecars with embeddings for search.

### `search_queries`
Query logs with metadata and latency tracking.

## Video Processing Pipeline

1. **Upload**: Client uploads to Supabase Storage via signed URL
2. **Enqueue**: API enqueues `process_video` task
3. **Download**: Worker downloads video from storage
4. **Extract Metadata**: FFprobe extracts duration, resolution, fps, etc.
5. **Scene Detection**: PySceneDetect finds scene boundaries
6. **Transcription**: OpenAI Whisper transcribes audio
7. **Visual Analysis**: GPT-4o analyzes keyframes per scene
8. **Embedding**: OpenAI text-embedding-3-small creates vectors
9. **Storage**: Scenes saved to database with embeddings
10. **Ready**: Video marked as READY for search

## Configuration

### API Service

- `API_HOST`: Host to bind (default: 0.0.0.0)
- `API_PORT`: Port to bind (default: 8000)
- `API_CORS_ORIGINS`: Allowed CORS origins (comma-separated)

### Worker Service

- `TEMP_DIR`: Working directory for video processing (default: /tmp/heimdex)
- `MAX_KEYFRAMES_PER_SCENE`: Max keyframes to extract (default: 3)
- `SCENE_DETECTOR`: Scene detection strategy (`adaptive` or `content`, default: `adaptive`)
- `SCENE_MIN_LEN_SECONDS`: Minimum scene length in seconds (default: 1.0)
- `SCENE_ADAPTIVE_THRESHOLD`: Threshold for adaptive detector (default: 3.0)
- `SCENE_CONTENT_THRESHOLD`: Threshold for content detector (default: 27.0)
- `MAX_SCENE_WORKERS`: Max concurrent scenes to process in parallel (default: 3)
- `VISUAL_SEMANTICS_MODEL`: Model for visual analysis (default: `gpt-4o-mini`)
- `EMBEDDING_MODEL`: OpenAI embedding model (default: `text-embedding-3-small`)
- `EMBEDDING_DIMENSIONS`: Vector dimensions (default: 1536)

### Frontend Service

- `NEXT_PUBLIC_SUPABASE_URL`: Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase anonymous public key
- `NEXT_PUBLIC_API_URL`: API service URL (default: `http://localhost:8000`)

## Troubleshooting

### Worker fails with FFmpeg errors
Ensure FFmpeg is installed in the worker container (already included in Dockerfile).

### Videos stuck in PROCESSING
Check worker logs: `docker-compose logs worker`

### Search returns no results
- Ensure video is marked as READY
- Lower the similarity threshold in search request
- Check that scenes have embeddings: `SELECT COUNT(*) FROM video_scenes WHERE embedding IS NOT NULL;`

### Upload fails
- Check Supabase storage bucket is public
- Verify storage policies allow authenticated uploads
- Check file size limits

## Production Deployment

Ready to deploy Heimdex? See the comprehensive deployment guide:

📘 **[docs/deployment/README.md](docs/deployment/README.md)** - Complete deployment guide with platform comparisons

**Quick Start**:
1. Run pre-deployment check: `./scripts/pre-deploy-check.sh`
2. Choose platform (Railway.app recommended)
3. Follow step-by-step guide in [docs/deployment/README.md](docs/deployment/README.md)
4. Use [docs/deployment/CHECKLIST.md](docs/deployment/CHECKLIST.md) to track progress

**Recommended Platform**: [Railway.app](https://railway.app)
- Native Docker Compose support
- Managed Redis included
- Automatic GitHub deploys
- Simple setup, production-ready
- ~$20-30/month

**Alternative Platforms**: Render.com, DigitalOcean App Platform, Fly.io

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[Architecture](docs/architecture/)** - System design and architecture patterns
- **[Deployment](docs/deployment/)** - Deployment guides and checklists
- **[Features](docs/features/)** - Feature specifications and admin metrics
- **[Implementation](docs/implementation/)** - Phase summaries and migration guides
- **[Operations](docs/operations/)** - Backfill, troubleshooting, and maintenance
- **[Search](docs/search/)** - Search pipeline and hybrid search documentation
- **[Testing](docs/testing/)** - Testing guides and procedures

Start here: **[docs/README.md](docs/README.md)**

## Production Considerations

Key considerations for production deployment:

1. **Environment Variables**: Use platform secrets management (never commit `.env`)
2. **Database**: Use Supabase connection pooler for better performance
3. **Storage**: Supabase Storage includes CDN
4. **Worker Scaling**: Increase Dramatiq worker count for parallel processing
5. **Monitoring**: Add error tracking (Sentry), uptime monitoring (Better Uptime)
6. **Rate Limiting**: Add rate limiting to API endpoints if needed
7. **Video Validation**: File type and size validation already implemented
8. **Backup**: Supabase provides automatic daily backups (paid plans)
9. **HTTPS**: Automatic on Railway/Render
10. **Costs**: Budget ~$20-50/month (infrastructure + OpenAI API usage)

See [docs/deployment/README.md](docs/deployment/README.md) for detailed guidance on all topics.

## Technology Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **API**: FastAPI, Python 3.11+
- **Worker**: Dramatiq, Python 3.11+
- **Database**: Supabase Postgres + pgvector
- **Storage**: Supabase Storage
- **Auth**: Supabase Auth (JWT)
- **Queue**: Redis
- **AI**: OpenAI (Whisper, GPT-4o, Embeddings)
- **Video Processing**: FFmpeg, PySceneDetect
- **Container Orchestration**: Docker Compose
- **Package Management**: uv (Python), npm (Node.js)

## License

MIT

## Contributing

This is a demo project. Feel free to fork and adapt for your needs!
