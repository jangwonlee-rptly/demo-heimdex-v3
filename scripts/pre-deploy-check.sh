#!/bin/bash

# Heimdex Pre-Deployment Checklist Script
# Run this before deploying to verify everything is ready

set -e

echo "🚀 Heimdex Pre-Deployment Checklist"
echo "====================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Function to run a check
run_check() {
    local description=$1
    local command=$2

    echo -ne "Checking: $description... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# Function for manual checks
manual_check() {
    local description=$1
    echo -e "${YELLOW}Manual:${NC} $description"
    ((WARNINGS++))
}

echo "🔧 System Checks"
echo "----------------"
run_check "Docker is installed" "command -v docker"
run_check "Docker Compose is installed" "command -v docker-compose || docker compose version"
run_check "Git is installed" "command -v git"
echo ""

echo "📦 Repository Checks"
echo "--------------------"
run_check "Git repository initialized" "git rev-parse --git-dir"
run_check "On main branch" "git branch --show-current | grep -q 'main'"
run_check ".env.example exists" "test -f .env.example"
run_check ".gitignore exists" "test -f .gitignore"
run_check ".env is gitignored" "git check-ignore .env"
echo ""

echo "🐳 Docker Checks"
echo "----------------"
run_check "API Dockerfile exists" "test -f services/api/Dockerfile"
run_check "Worker Dockerfile exists" "test -f services/worker/Dockerfile"
run_check "Frontend Dockerfile exists" "test -f services/frontend/Dockerfile"
run_check "docker-compose.yml exists" "test -f docker-compose.yml"

# Try to build (optional, can be slow)
echo -e "${BLUE}Info:${NC} Skipping Docker build test (run 'docker-compose build' manually to verify)"
echo ""

echo "📄 Configuration File Checks"
echo "----------------------------"
run_check "README.md exists" "test -f README.md"
run_check "LICENSE exists" "test -f LICENSE"
run_check "DEPLOYMENT.md exists" "test -f DEPLOYMENT.md"
run_check "package-lock.json exists" "test -f services/frontend/package-lock.json"
run_check ".gitattributes exists" "test -f .gitattributes"
echo ""

echo "🗄️  Database Checks"
echo "-------------------"
run_check "Initial schema migration exists" "test -f infra/migrations/001_initial_schema.sql"
run_check "pgvector migration exists" "test -f infra/migrations/002_enable_pgvector.sql"
manual_check "Verify migrations are run in Supabase (check manually)"
manual_check "Verify storage bucket exists (check Supabase dashboard)"
echo ""

echo "🔐 Security Checks"
echo "------------------"
if [ -f .env ]; then
    run_check ".env file is gitignored" "git check-ignore .env"

    # Check for placeholder values
    if grep -q "your-project.supabase.co" .env 2>/dev/null; then
        echo -e "${RED}✗${NC} .env contains placeholder values"
        ((CHECKS_FAILED++))
    else
        echo -e "${GREEN}✓${NC} .env appears to have real values"
        ((CHECKS_PASSED++))
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file not found (will need to set env vars in platform)"
    ((WARNINGS++))
fi
echo ""

echo "🔑 Environment Variables Check"
echo "------------------------------"
if [ -f .env ]; then
    # Source .env and run verification
    set -a
    source .env
    set +a

    if ./scripts/verify-env.sh > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} All required environment variables are set"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} Some environment variables are missing"
        ((CHECKS_FAILED++))
        echo "Run './scripts/verify-env.sh' for details"
    fi
else
    echo -e "${YELLOW}⚠${NC} Skipping env var check (.env not found)"
    ((WARNINGS++))
fi
echo ""

echo "📝 Manual Verification Required"
echo "--------------------------------"
manual_check "GitHub repository is created and code is pushed"
manual_check "Supabase project is created and configured"
manual_check "OpenAI API key has sufficient credits"
manual_check "DNS records ready (if using custom domain)"
echo ""

echo "====================================="
echo "📊 Pre-Deployment Check Summary"
echo "====================================="
echo -e "${GREEN}✓ Passed:${NC} $CHECKS_PASSED checks"
echo -e "${RED}✗ Failed:${NC} $CHECKS_FAILED checks"
echo -e "${YELLOW}⚠ Warnings:${NC} $WARNINGS items need manual verification"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ Pre-deployment checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Complete manual verification items above"
    echo "2. Choose deployment platform (see DEPLOYMENT.md)"
    echo "3. Deploy! 🚀"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some checks failed!${NC}"
    echo "Please fix the issues above before deploying."
    echo ""
    exit 1
fi
