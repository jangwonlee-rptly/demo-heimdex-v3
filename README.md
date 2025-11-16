# Heimdex - Vector Native Video Archive

A production-ready demo application that enables semantic search across videos using scene detection, AI-powered transcription, and vector embeddings.

## Features

- **User Authentication**: Signup/login with Supabase Auth
- **User Onboarding**: First-time user profile setup with marketing consent tracking
- **Video Upload**: Upload videos to Supabase Storage with progress tracking
- **Automated Processing**: Background worker processes videos into searchable scenes
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
- `SCENE_DETECTION_THRESHOLD`: PySceneDetect threshold (default: 27.0)
- `EMBEDDING_MODEL`: OpenAI embedding model (default: text-embedding-3-small)
- `EMBEDDING_DIMENSIONS`: Vector dimensions (default: 1536)

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

## Production Considerations

For production deployment, consider:

1. **Environment Variables**: Use secrets management (e.g., AWS Secrets Manager, HashiCorp Vault)
2. **Database**: Use Supabase connection pooler for better performance
3. **Storage**: Configure CDN for video delivery
4. **Worker Scaling**: Increase Dramatiq worker count for parallel processing
5. **Monitoring**: Add application monitoring (e.g., Sentry, DataDog)
6. **Rate Limiting**: Add rate limiting to API endpoints
7. **Video Validation**: Add file type and size validation
8. **Graceful Shutdown**: Implement proper signal handling in workers
9. **Backup**: Regular database backups
10. **HTTPS**: Use reverse proxy (nginx, Caddy) with SSL certificates

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
