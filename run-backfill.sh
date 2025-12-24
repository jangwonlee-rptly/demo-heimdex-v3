#!/bin/bash
#
# Backfill Script Runner (Docker)
#
# This script runs the Phase 2 video timing backfill in the Docker environment.
# It connects to the running API container and executes the backfill script.
#
# Usage:
#   ./run-backfill.sh              # Execute backfill
#   ./run-backfill.sh --dry-run    # Preview what would be updated
#
# Prerequisites:
#   - Docker Compose services must be running (docker-compose up -d)
#   - Database migrations 019 and 020 must be applied
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Phase 2 Video Timing Backfill (Docker)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker Compose is running
if ! docker-compose ps | grep -q "api.*Up"; then
    echo -e "${RED}ERROR: API container is not running${NC}"
    echo ""
    echo "Please start Docker Compose first:"
    echo "  docker-compose up -d"
    echo ""
    exit 1
fi

# Check if database is accessible
echo -e "${YELLOW}Checking database connection...${NC}"
if ! docker-compose exec -T api python3 -c "from src.adapters.database import db; db.client.table('videos').select('id').limit(1).execute()" 2>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to database${NC}"
    echo ""
    echo "Please check:"
    echo "  1. Database is running and accessible"
    echo "  2. DATABASE_URL environment variable is set correctly"
    echo "  3. Migrations 019 and 020 have been applied"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Database connection OK${NC}"
echo ""

# Parse arguments
DRY_RUN=""
if [ "$1" = "--dry-run" ]; then
    DRY_RUN="--dry-run"
    echo -e "${YELLOW}Running in DRY RUN mode (no changes will be made)${NC}"
    echo ""
fi

# Run the backfill script in the API container
echo -e "${BLUE}Running backfill script...${NC}"
echo ""

docker-compose exec api python3 -m src.scripts.backfill_video_timing $DRY_RUN

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Backfill script completed${NC}"
echo -e "${GREEN}========================================${NC}"

# Show next steps if not dry run
if [ -z "$DRY_RUN" ]; then
    echo ""
    echo "Next steps:"
    echo "  1. Verify backfilled data in database:"
    echo "     docker-compose exec -T db psql -U postgres -d postgres -c \"SELECT COUNT(*) FROM videos WHERE processing_finished_at IS NOT NULL;\""
    echo ""
    echo "  2. Test Phase 2 endpoints:"
    echo "     curl -H 'Authorization: Bearer \$TOKEN' http://localhost:8000/v1/admin/performance/latency?range=7d"
    echo ""
fi
