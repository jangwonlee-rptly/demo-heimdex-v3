#!/bin/bash
# Test runner script for Heimdex services
# This script runs tests in Docker containers

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

# Help message
show_help() {
    cat << EOF
Usage: ./scripts/test.sh [OPTIONS] [SERVICE]

Run tests for Heimdex services in Docker containers.

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Run tests with verbose output
    -c, --coverage          Generate HTML coverage report
    -u, --unit              Run only unit tests
    -i, --integration       Run only integration tests
    -w, --watch             Watch mode (rebuild and rerun on change)
    --no-cache              Build without using cache
    --shell                 Drop into test container shell (for debugging)

SERVICE:
    api                     Run API tests (default)
    worker                  Run worker tests
    all                     Run all tests

EXAMPLES:
    ./scripts/test.sh                    # Run API tests
    ./scripts/test.sh --coverage         # Run with HTML coverage report
    ./scripts/test.sh --unit api         # Run only API unit tests
    ./scripts/test.sh --shell api        # Debug tests in container shell
    ./scripts/test.sh all                # Run all service tests

EOF
}

# Default values
SERVICE="api"
VERBOSE=""
COVERAGE=""
TEST_FILTER=""
BUILD_ARGS=""
WATCH_MODE=false
SHELL_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov-report=html"
            shift
            ;;
        -u|--unit)
            TEST_FILTER="-m unit"
            shift
            ;;
        -i|--integration)
            TEST_FILTER="-m integration"
            shift
            ;;
        -w|--watch)
            WATCH_MODE=true
            shift
            ;;
        --no-cache)
            BUILD_ARGS="--no-cache"
            shift
            ;;
        --shell)
            SHELL_MODE=true
            shift
            ;;
        api|worker|all)
            SERVICE=$1
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Run tests for a service
run_tests() {
    local service=$1
    local service_name="${service}-test"

    print_info "Running tests for ${service} service..."

    if [ "$SHELL_MODE" = true ]; then
        print_info "Starting interactive shell in test container..."
        docker compose -f docker-compose.test.yml run --rm \
            ${service_name} \
            /bin/bash
        return
    fi

    # Build the test image
    print_info "Building test image..."
    docker compose -f docker-compose.test.yml build ${BUILD_ARGS} ${service_name}

    # Run tests
    print_info "Executing tests..."
    if docker compose -f docker-compose.test.yml run --rm \
        ${service_name} \
        pytest ${VERBOSE} ${TEST_FILTER} ${COVERAGE}; then
        print_success "${service} tests passed!"

        if [ -n "$COVERAGE" ]; then
            print_info "Coverage report generated at: services/${service}/htmlcov/index.html"
        fi
        return 0
    else
        print_error "${service} tests failed!"
        return 1
    fi
}

# Main execution
main() {
    print_info "Heimdex Test Runner"
    echo ""

    if [ "$SERVICE" = "all" ]; then
        print_info "Running tests for all services..."
        FAILED_SERVICES=""

        for svc in api worker; do
            if run_tests "$svc"; then
                echo ""
            else
                FAILED_SERVICES="${FAILED_SERVICES} ${svc}"
            fi
        done

        echo ""
        if [ -z "$FAILED_SERVICES" ]; then
            print_success "All tests passed!"
            exit 0
        else
            print_error "Tests failed for:${FAILED_SERVICES}"
            exit 1
        fi
    else
        run_tests "$SERVICE"
    fi
}

# Run main
main
