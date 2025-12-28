# Backfill Quick Start (Docker)

Run the Phase 2 video timing backfill in your dockerized environment.

---

## TL;DR

```bash
# From project root directory

# 1. Dry run first (preview changes)
./run-backfill.sh --dry-run

# 2. Execute backfill
./run-backfill.sh
```

---

## Prerequisites Checklist

- [ ] Docker Compose services running: `docker-compose ps`
- [ ] Migration 019 applied (timing columns)
- [ ] Migration 020 applied (RPC functions)
- [ ] Database accessible from API container

---

## Commands

### Using Helper Script (Recommended)

```bash
# Dry run
./run-backfill.sh --dry-run

# Execute
./run-backfill.sh
```

### Using Docker Compose Directly

```bash
# Dry run
docker-compose exec api python3 -m src.scripts.backfill_video_timing --dry-run

# Execute
docker-compose exec api python3 -m src.scripts.backfill_video_timing
```

### Using Interactive Shell

```bash
# Enter container
docker-compose exec api bash

# Inside container
python3 -m src.scripts.backfill_video_timing --dry-run
python3 -m src.scripts.backfill_video_timing
```

---

## What Gets Backfilled

✅ **Backfilled:**
- `processing_finished_at` = `updated_at` (for throughput trends)

❌ **NOT Backfilled (intentionally):**
- `processing_started_at` - NULL (no precise data)
- `processing_duration_ms` - NULL (no precise data)
- `queued_at` - NULL (no precise data)

**Why?** We only backfill data we can accurately derive. Fabricating timing data would corrupt metrics.

---

## Verify Results

```bash
# Check how many videos were backfilled
docker-compose exec api python3 -c "
from src.adapters.database import db
response = db.client.table('videos').select('processing_finished_at').is_('processing_finished_at', 'not.null').execute()
print(f'Videos backfilled: {len(response.data)}')
"
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| API container not running | `docker-compose up -d` |
| Cannot connect to database | Check DATABASE_URL env var |
| Module not found | `docker-compose up --build -d` |
| Permission denied | `chmod +x run-backfill.sh` |

---

## Full Documentation

- **Detailed guide:** `DOCKER_BACKFILL_GUIDE.md`
- **Phase 2 overview:** `ADMIN_METRICS_PHASE2_README.md`
