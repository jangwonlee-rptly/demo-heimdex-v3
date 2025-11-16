#!/bin/bash

# Heimdex Environment Variable Verification Script
# This script checks that all required environment variables are set

set -e

echo "🔍 Heimdex Environment Verification"
echo "===================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
MISSING=0
PRESENT=0

# Function to check if variable is set
check_var() {
    local var_name=$1
    local var_value=${!var_name}
    local is_secret=${2:-false}

    if [ -z "$var_value" ]; then
        echo -e "${RED}✗${NC} $var_name - MISSING"
        ((MISSING++))
        return 1
    else
        if [ "$is_secret" = "true" ]; then
            echo -e "${GREEN}✓${NC} $var_name - Set (hidden)"
        else
            echo -e "${GREEN}✓${NC} $var_name - $var_value"
        fi
        ((PRESENT++))
        return 0
    fi
}

echo "📋 Checking Supabase Configuration..."
echo "--------------------------------------"
check_var "SUPABASE_URL"
check_var "SUPABASE_ANON_KEY" true
check_var "SUPABASE_SERVICE_ROLE_KEY" true
check_var "SUPABASE_JWT_SECRET" true
check_var "DATABASE_URL" true
echo ""

echo "🤖 Checking OpenAI Configuration..."
echo "--------------------------------------"
check_var "OPENAI_API_KEY" true
echo ""

echo "🌐 Checking API Configuration..."
echo "--------------------------------------"
if [ -z "$API_CORS_ORIGINS" ]; then
    echo -e "${YELLOW}⚠${NC} API_CORS_ORIGINS - Not set (will use default)"
else
    check_var "API_CORS_ORIGINS"
fi
echo ""

echo "📦 Checking Redis Configuration..."
echo "--------------------------------------"
if [ -z "$REDIS_URL" ]; then
    echo -e "${YELLOW}⚠${NC} REDIS_URL - Not set (will use redis://redis:6379/0)"
else
    check_var "REDIS_URL" true
fi
echo ""

echo "🎨 Checking Frontend Configuration..."
echo "--------------------------------------"
check_var "NEXT_PUBLIC_SUPABASE_URL"
check_var "NEXT_PUBLIC_SUPABASE_ANON_KEY" true
if [ -z "$NEXT_PUBLIC_API_URL" ]; then
    echo -e "${YELLOW}⚠${NC} NEXT_PUBLIC_API_URL - Not set (will use http://localhost:8000)"
else
    check_var "NEXT_PUBLIC_API_URL"
fi
echo ""

echo "===================================="
echo "📊 Summary"
echo "===================================="
echo -e "${GREEN}✓ Present:${NC} $PRESENT variables"
echo -e "${RED}✗ Missing:${NC} $MISSING variables"
echo ""

if [ $MISSING -gt 0 ]; then
    echo -e "${RED}❌ Some required environment variables are missing!${NC}"
    echo "Please set them before deploying."
    echo ""
    echo "💡 Tip: Copy .env.example to .env and fill in your values:"
    echo "   cp .env.example .env"
    echo "   nano .env"
    exit 1
else
    echo -e "${GREEN}✅ All required environment variables are set!${NC}"
    echo "You're ready to deploy! 🚀"
    exit 0
fi
