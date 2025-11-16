#!/bin/bash

# Heimdex Railway Deployment Helper Script
# This script guides you through deploying to Railway using the CLI

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════╗"
echo "║  Heimdex Railway Deployment Helper  ║"
echo "╔══════════════════════════════════════╗"
echo -e "${NC}"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI is not installed${NC}"
    echo "Install it with: npm i -g @railway/cli"
    exit 1
fi

echo -e "${GREEN}✓ Railway CLI is installed${NC}"
echo ""

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Railway${NC}"
    echo "Run: railway login"
    exit 1
fi

echo -e "${GREEN}✓ Logged in to Railway${NC}"
echo ""

# Function to prompt for continuation
prompt_continue() {
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read -r
}

# Function to get user input
get_input() {
    local prompt=$1
    local var_name=$2
    echo -e "${BLUE}$prompt${NC}"
    read -r input
    eval "$var_name='$input'"
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Initialize Railway Project"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Choose an option:"
echo "1) Create a new Railway project"
echo "2) Link to an existing Railway project"
echo ""
get_input "Enter choice (1 or 2):" choice

if [ "$choice" = "1" ]; then
    echo ""
    echo "Creating new Railway project..."
    railway init
elif [ "$choice" = "2" ]; then
    echo ""
    echo "Linking to existing project..."
    railway link
else
    echo -e "${RED}Invalid choice${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Project initialized${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Create Redis Database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Railway databases must be created via the dashboard."
echo "Opening Railway dashboard..."
echo ""
railway open
echo ""
echo "In the dashboard:"
echo "1. Click '+ New'"
echo "2. Select 'Database' → 'Redis'"
echo "3. Wait for Redis to be created"
echo ""
echo "Return here when done."
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Gather Your Credentials"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "You'll need the following credentials. Have them ready:"
echo ""
echo "From Supabase (https://supabase.com/dashboard):"
echo "  - SUPABASE_URL"
echo "  - SUPABASE_ANON_KEY"
echo "  - SUPABASE_SERVICE_ROLE_KEY"
echo "  - SUPABASE_JWT_SECRET"
echo "  - DATABASE_URL"
echo ""
echo "From OpenAI (https://platform.openai.com/api-keys):"
echo "  - OPENAI_API_KEY"
echo ""
prompt_continue

# Collect credentials
echo ""
echo "Enter your credentials:"
echo ""
get_input "SUPABASE_URL: " SUPABASE_URL
get_input "SUPABASE_ANON_KEY: " SUPABASE_ANON_KEY
get_input "SUPABASE_SERVICE_ROLE_KEY: " SUPABASE_SERVICE_ROLE_KEY
get_input "SUPABASE_JWT_SECRET: " SUPABASE_JWT_SECRET
get_input "DATABASE_URL: " DATABASE_URL
get_input "OPENAI_API_KEY: " OPENAI_API_KEY

echo ""
echo -e "${GREEN}✓ Credentials collected${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Deploy API Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Creating API service..."
railway service create api

echo "Setting API environment variables..."
railway service --name api

railway variables set SUPABASE_URL="$SUPABASE_URL"
railway variables set SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
railway variables set SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY"
railway variables set SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET"
railway variables set DATABASE_URL="$DATABASE_URL"
railway variables set OPENAI_API_KEY="$OPENAI_API_KEY"
railway variables set REDIS_URL='${{Redis.REDIS_URL}}'
railway variables set API_CORS_ORIGINS="http://localhost:3000"

echo ""
echo "Deploying API..."
cd services/api
railway up --service api

echo ""
echo "Generating public domain for API..."
railway domain

echo ""
echo "Note the API domain (you'll need it for frontend)"
get_input "Enter the API domain (e.g., api-production-abc123.up.railway.app): " API_DOMAIN

cd ../..
echo ""
echo -e "${GREEN}✓ API service deployed${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Deploy Worker Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Creating Worker service..."
railway service create worker

echo "Setting Worker environment variables..."
railway service --name worker

railway variables set SUPABASE_URL="$SUPABASE_URL"
railway variables set SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY"
railway variables set DATABASE_URL="$DATABASE_URL"
railway variables set OPENAI_API_KEY="$OPENAI_API_KEY"
railway variables set REDIS_URL='${{Redis.REDIS_URL}}'
railway variables set TEMP_DIR="/tmp/heimdex"

echo ""
echo "Deploying Worker..."
cd services/worker
railway up --service worker

cd ../..
echo ""
echo -e "${GREEN}✓ Worker service deployed${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Deploy Frontend Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Creating Frontend service..."
railway service create frontend

echo "Setting Frontend environment variables..."
railway service --name frontend

railway variables set NEXT_PUBLIC_SUPABASE_URL="$SUPABASE_URL"
railway variables set NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
railway variables set NEXT_PUBLIC_API_URL="https://$API_DOMAIN"

echo ""
echo "Deploying Frontend..."
cd services/frontend
railway up --service frontend

echo ""
echo "Generating public domain for Frontend..."
railway domain

echo ""
echo "Note the Frontend domain (this is your app URL)"
get_input "Enter the Frontend domain (e.g., frontend-production-xyz.up.railway.app): " FRONTEND_DOMAIN

cd ../..
echo ""
echo -e "${GREEN}✓ Frontend service deployed${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Update CORS Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Updating API CORS to include Frontend domain..."
railway service --name api
railway variables set API_CORS_ORIGINS="https://$FRONTEND_DOMAIN"

echo ""
echo "Redeploying API with updated CORS..."
cd services/api
railway up --service api
cd ../..

echo ""
echo -e "${GREEN}✓ CORS updated${NC}"
prompt_continue

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}Your Heimdex application is now live!${NC}"
echo ""
echo "Frontend URL: https://$FRONTEND_DOMAIN"
echo "API URL: https://$API_DOMAIN"
echo ""
echo "Next steps:"
echo "1. Visit the Frontend URL to test your app"
echo "2. Sign up / Log in"
echo "3. Upload a test video"
echo "4. Check logs: railway logs -f"
echo ""
echo "View all services:"
echo "  railway open"
echo ""
echo "Check service status:"
echo "  railway service --name api && railway status"
echo "  railway service --name worker && railway status"
echo "  railway service --name frontend && railway status"
echo ""
echo -e "${BLUE}Happy deploying! 🚀${NC}"
echo ""
