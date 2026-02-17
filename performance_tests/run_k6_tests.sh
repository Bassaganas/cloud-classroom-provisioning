#!/bin/bash

###############################################################################
# k6 Test Runner Script
# 
# This script helps you run the k6 performance tests for Lambda user management
# 
# Usage:
#   ./run_k6_tests.sh scenario1
#   ./run_k6_tests.sh scenario2
#   ./run_k6_tests.sh all
#   ./run_k6_tests.sh prepare --count 20
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
USER_MANAGEMENT_URL="${USER_MANAGEMENT_URL:-}"
INSTANCE_MANAGER_URL="${INSTANCE_MANAGER_URL:-}"
INSTANCE_MANAGER_PASSWORD="${INSTANCE_MANAGER_PASSWORD:-}"
INSTANCE_COUNT="${INSTANCE_COUNT:-20}"
INSTANCE_TYPE="${INSTANCE_TYPE:-pool}"

# Functions
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_k6_installed() {
    if ! command -v k6 &> /dev/null; then
        print_error "k6 is not installed!"
        echo "Install k6:"
        echo "  macOS: brew install k6"
        echo "  Linux: See https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
    print_success "k6 is installed ($(k6 version))"
}

check_python_installed() {
    if ! command -v python3 &> /dev/null; then
        print_error "python3 is not installed!"
        exit 1
    fi
    print_success "python3 is installed"
}

check_environment() {
    local missing_vars=()
    
    if [ -z "$USER_MANAGEMENT_URL" ]; then
        missing_vars+=("USER_MANAGEMENT_URL")
    fi
    
    if [ -z "$INSTANCE_MANAGER_URL" ]; then
        missing_vars+=("INSTANCE_MANAGER_URL")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Set them with:"
        echo "  export USER_MANAGEMENT_URL='https://testus-patronus.testingfantasy.com/'"
        echo "  export INSTANCE_MANAGER_URL='https://ec2-management.testingfantasy.com/'"
        echo ""
        echo "Optional:"
        echo "  export INSTANCE_MANAGER_PASSWORD='your-password'"
        exit 1
    fi
    
    print_success "Environment variables are set"
    print_info "  USER_MANAGEMENT_URL: $USER_MANAGEMENT_URL"
    print_info "  INSTANCE_MANAGER_URL: $INSTANCE_MANAGER_URL"
    if [ -n "$INSTANCE_MANAGER_PASSWORD" ]; then
        print_info "  INSTANCE_MANAGER_PASSWORD: [SET]"
    else
        print_warning "  INSTANCE_MANAGER_PASSWORD: [NOT SET] - Instance preparation may fail if auth is required"
    fi
}

check_instance_pool() {
    local expected_count="${1:-$INSTANCE_COUNT}"
    
    # Use Python to check instance status
    # This is a best-effort check - if it fails, we'll continue anyway
    python3 -c "
import requests
import sys
import os

url = os.environ.get('INSTANCE_MANAGER_URL', '')
password = os.environ.get('INSTANCE_MANAGER_PASSWORD', '')
expected = int('${expected_count}')

if not url:
    sys.exit(1)

# Try to authenticate if password is provided
auth_cookie = None
if password:
    try:
        auth_response = requests.post(
            f'{url}/login',
            json={'password': password},
            timeout=10
        )
        if auth_response.status_code == 200:
            cookies = auth_response.cookies
            if cookies:
                auth_cookie = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    except:
        pass

# Check instance list
try:
    headers = {}
    if auth_cookie:
        headers['Cookie'] = auth_cookie
    
    response = requests.get(f'{url}/list', headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if 'instances' in data:
            # Count all pool instances (not just "available") - instances may be in pending/running state
            all_pool_instances = [i for i in data['instances'] 
                                if i.get('type') == 'pool']
            available_pool_instances = [i for i in all_pool_instances 
                                      if i.get('status') == 'available' or i.get('state') in ['running', 'stopped', 'pending']]
            
            # For large batches, be lenient (accept 80%+)
            min_required = int(expected * 0.8) if expected > 50 else expected
            count = len(all_pool_instances)
            available_count = len(available_pool_instances)
            
            print(f'Found {count} total pool instances, {available_count} available (expected: {expected})', file=sys.stderr)
            
            # Accept if we have at least min_required instances
            if count >= min_required:
                sys.exit(0)
            else:
                sys.exit(1)
    elif response.status_code == 401:
        # Authentication required but failed - assume instances might exist
        print('Authentication required - cannot verify instance pool', file=sys.stderr)
        sys.exit(1)
    else:
        sys.exit(1)
except Exception as e:
    print(f'Error checking instance pool: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1
    
    local result=$?
    if [ $result -eq 0 ]; then
        print_success "Instance pool is ready"
        return 0
    else
        return 1
    fi
}

prepare_instances() {
    local count="${1:-$INSTANCE_COUNT}"
    local type="${2:-$INSTANCE_TYPE}"
    
    print_header "Preparing Instance Pool"
    
    check_python_installed
    
    # Check if password is required but not set
    if [ -z "$INSTANCE_MANAGER_PASSWORD" ]; then
        print_warning "INSTANCE_MANAGER_PASSWORD is not set"
        print_info "If authentication is required, set it with:"
        print_info "  export INSTANCE_MANAGER_PASSWORD='your-password'"
        print_info ""
        print_info "Attempting to create instances without password..."
    fi
    
    # Build command array to properly handle password with special characters
    local cmd_args=(
        "python3" "prepare_instances.py"
        "--url" "$INSTANCE_MANAGER_URL"
        "--count" "$count"
        "--type" "$type"
        "--verify"
    )
    
    if [ -n "$INSTANCE_MANAGER_PASSWORD" ]; then
        cmd_args+=("--password" "$INSTANCE_MANAGER_PASSWORD")
    fi
    
    print_info "Creating $count $type instances..."
    
    if "${cmd_args[@]}"; then
        print_success "Instance pool prepared successfully"
        return 0
    else
        print_error "Failed to prepare instance pool"
        if [ -z "$INSTANCE_MANAGER_PASSWORD" ]; then
            print_info "This might be due to missing authentication."
            print_info "Set INSTANCE_MANAGER_PASSWORD and try again:"
            print_info "  export INSTANCE_MANAGER_PASSWORD='your-password'"
        fi
        return 1
    fi
}

run_scenario1() {
    print_header "Running Scenario 1: New User Instance Assignment"
    
    check_k6_installed
    check_environment
    
    # Instance pool size: use INSTANCE_POOL_SIZE if set, otherwise default to 20
    # For conference scenario, use 100 if not specified
    local pool_size="${INSTANCE_POOL_SIZE:-${INSTANCE_COUNT:-20}}"
    
    # Calculate test duration based on pool size and burst pattern
    # Conference burst pattern: Ramp up 10s, then maintain 2 users/second
    # Duration = ramp-up (10s) + sustained (pool_size / 2) + buffer
    # Note: 2 users/sec = 6 IAM calls/sec, slightly over AWS limit (5/sec) but manageable with retries
    local ramp_up_duration=10
    local peak_rate=2
    local sustained_duration=$(( (pool_size / peak_rate) + 10 ))
    local test_duration=$(( ramp_up_duration + sustained_duration ))
    local test_duration_minutes=$(( test_duration / 60 ))
    
    print_info "Configuration:"
    print_info "  Instance Pool Size: $pool_size"
    print_info "  Expected Users: $pool_size (matches instance pool size)"
    print_info "  Test Pattern: Conference burst (ramp-up 10s, then 2 users/sec)"
    print_info "  Max Virtual Users: $pool_size"
    print_info "  Estimated Duration: ~${test_duration} seconds (${test_duration_minutes} minutes)"
    print_warning "  Note: 2 users/sec = 6 IAM calls/sec (slightly over 5/sec limit, some throttling expected)"
    if [ "$pool_size" -ge 100 ]; then
        print_warning "Large scale test: Users will arrive in burst pattern over ~${test_duration_minutes} minutes"
    fi
    
    # Check if instances are available
    print_info "\n🔍 Checking instance pool status..."
    if ! check_instance_pool "$pool_size"; then
        print_warning "Instance pool may not be ready or insufficient instances available"
        
        # Check if password is set
        if [ -z "$INSTANCE_MANAGER_PASSWORD" ]; then
            print_warning "INSTANCE_MANAGER_PASSWORD is not set - cannot prepare instances automatically"
            print_info "Set it with: export INSTANCE_MANAGER_PASSWORD='your-password'"
            print_info "Or prepare instances manually using: ./run_k6_tests.sh prepare --count $pool_size"
            print_info "\nContinuing with test - some requests may fail if instances aren't ready"
            sleep 2
        else
            print_info "Would you like to prepare instances now? (y/N)"
            read -t 10 -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                prepare_instances "$pool_size" "pool"
                if [ $? -eq 0 ]; then
                    print_info "Waiting 1 min for instances to initialize..."
                    sleep 60
                else
                    print_error "Failed to prepare instances. Continuing anyway..."
                    sleep 2
                fi
            else
                print_warning "Continuing with test - some requests may fail if instances aren't ready"
                sleep 2
            fi
        fi
    fi
    
    local output_file="scenario1_results_$(date +%Y%m%d_%H%M%S).txt"
    
    print_info "\nRunning test... (output will be saved to $output_file)"
    
    k6 run \
        -e "USER_MANAGEMENT_URL=$USER_MANAGEMENT_URL" \
        -e "INSTANCE_POOL_SIZE=$pool_size" \
        k6_scenario1_new_users.js \
        | tee "$output_file"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Scenario 1 completed successfully"
        print_info "Results saved to: $output_file"
        print_info "Summary JSON: summary.json"
    else
        print_error "Scenario 1 failed"
        exit 1
    fi
}

run_scenario2() {
    print_header "Running Scenario 2: User Instance Persistence"
    
    check_k6_installed
    check_environment
    
    local num_users="${NUM_USERS:-10}"
    local refreshes="${REFRESHES_PER_USER:-10}"
    local iterations=$((num_users * (refreshes + 1)))  # 1 initial + N refreshes
    
    # Instance pool size: use INSTANCE_POOL_SIZE if set, otherwise default to num_users
    # This allows users to specify a larger pool if needed
    local pool_size="${INSTANCE_POOL_SIZE:-${num_users}}"
    
    # Ensure we have at least enough instances for the number of users
    local min_instances=$num_users
    if [ "$pool_size" -lt "$min_instances" ]; then
        print_warning "Instance pool size ($pool_size) is less than number of users ($num_users)"
        print_warning "Setting pool size to $min_instances to match user count"
        pool_size=$min_instances
    fi
    
    print_info "Configuration:"
    print_info "  Users: $num_users"
    print_info "  Refreshes per user: $refreshes"
    print_info "  Total iterations: $iterations"
    print_info "  Instance Pool Size: $pool_size"
    print_info "  Minimum instances needed: $min_instances"
    
    # Check if instances are available
    print_info "\n🔍 Checking instance pool status..."
    if ! check_instance_pool "$min_instances"; then
        print_warning "Instance pool may not be ready or insufficient instances available"
        print_warning "Scenario 2 requires at least $min_instances available pool instances"
        print_info "Would you like to prepare $pool_size instances now? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            prepare_instances "$pool_size" "pool"
            if [ $? -eq 0 ]; then
                print_info "Waiting 1 min for instances to initialize..."
                sleep 60
            else
                print_error "Failed to prepare instances"
                exit 1
            fi
        else
            print_warning "Continuing without instance pool preparation - test may fail"
        fi
    fi
    
    local output_file="scenario2_results_$(date +%Y%m%d_%H%M%S).txt"
    
    print_info "\nRunning test... (output will be saved to $output_file)"
    
    k6 run \
        --vus "$num_users" \
        --iterations "$iterations" \
        -e "USER_MANAGEMENT_URL=$USER_MANAGEMENT_URL" \
        -e "NUM_USERS=$num_users" \
        -e "REFRESHES_PER_USER=$refreshes" \
        -e "INSTANCE_POOL_SIZE=$pool_size" \
        k6_scenario2_user_persistence.js \
        | tee "$output_file"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Scenario 2 completed successfully"
        print_info "Results saved to: $output_file"
        print_info "Summary JSON: summary.json"
    else
        print_error "Scenario 2 failed"
        exit 1
    fi
}

run_scenario3() {
    print_header "Running Scenario 3: Instance Termination and Reassignment"
    
    check_k6_installed
    check_environment
    
    # Default to 10 users, but support larger scales for conference testing
    local num_users="${NUM_USERS:-10}"
    # For termination test, we terminate half the users' instances
    # So we need: num_users + (num_users / 2) instances minimum
    local min_pool_size=$((num_users + (num_users / 2)))
    local pool_size="${INSTANCE_POOL_SIZE:-${min_pool_size}}"
    
    print_info "Configuration:"
    print_info "  Users: $num_users"
    print_info "  Users to terminate: $((num_users / 2)) (first half)"
    print_info "  Instance Pool Size: $pool_size"
    print_info "  Test: Terminate instances and verify automatic reassignment"
    
    # Check if instances are available
    print_info "\n🔍 Checking instance pool status..."
    if ! check_instance_pool "$pool_size"; then
        print_warning "Instance pool may not be ready"
        print_info "Would you like to prepare instances now? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            prepare_instances "$pool_size" "pool"
            if [ $? -eq 0 ]; then
                print_info "Waiting 1 min for instances to initialize..."
                sleep 60
            fi
        fi
    fi
    
    local output_file="scenario3_results_$(date +%Y%m%d_%H%M%S).txt"
    print_info "\nRunning test... (output will be saved to $output_file)"
    
    # Note: Scenario 3 needs more instances than users because it terminates some
    # We need at least (num_users + num_users_to_terminate) instances
    # For termination, we terminate half the users' instances
    local users_to_terminate=$((num_users / 2))
    local min_pool_size=$((num_users + users_to_terminate))
    if [ "$pool_size" -lt "$min_pool_size" ]; then
        print_warning "Pool size ($pool_size) may be too small for termination test"
        print_info "Recommended: at least $min_pool_size instances (users + terminated instances)"
        print_info "Continuing anyway..."
    fi
    
    k6 run \
        -e "USER_MANAGEMENT_URL=$USER_MANAGEMENT_URL" \
        -e "INSTANCE_MANAGER_URL=$INSTANCE_MANAGER_URL" \
        -e "INSTANCE_MANAGER_PASSWORD=$INSTANCE_MANAGER_PASSWORD" \
        -e "NUM_USERS=$num_users" \
        -e "INSTANCE_POOL_SIZE=$pool_size" \
        k6_scenario3_instance_termination.js \
        | tee "$output_file"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Scenario 3 completed successfully"
        print_info "Results saved to: $output_file"
    else
        print_error "Scenario 3 failed"
        exit 1
    fi
}

run_scenario4() {
    print_header "Running Scenario 4: Pool Exhaustion and Recovery"
    
    check_k6_installed
    check_environment
    
    local num_users="${NUM_USERS:-15}"
    local pool_size="${INSTANCE_POOL_SIZE:-10}"  # Smaller pool to test exhaustion
    
    print_info "Configuration:"
    print_info "  Users: $num_users"
    print_info "  Instance Pool Size: $pool_size (smaller than users to test exhaustion)"
    print_info "  Test: Verify behavior when pool is exhausted"
    
    # Check if instances are available
    print_info "\n🔍 Checking instance pool status..."
    if ! check_instance_pool "$pool_size"; then
        print_warning "Instance pool may not be ready"
        print_info "Would you like to prepare $pool_size instances now? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            prepare_instances "$pool_size" "pool"
            if [ $? -eq 0 ]; then
                print_info "Waiting 1 min for instances to initialize..."
                sleep 60
            fi
        fi
    fi
    
    local output_file="scenario4_results_$(date +%Y%m%d_%H%M%S).txt"
    print_info "\nRunning test... (output will be saved to $output_file)"
    
    k6 run \
        -e "USER_MANAGEMENT_URL=$USER_MANAGEMENT_URL" \
        -e "NUM_USERS=$num_users" \
        -e "INSTANCE_POOL_SIZE=$pool_size" \
        k6_scenario4_pool_exhaustion.js \
        | tee "$output_file"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Scenario 4 completed successfully"
        print_info "Results saved to: $output_file"
    else
        print_error "Scenario 4 failed"
        exit 1
    fi
}

run_scenario5() {
    print_header "Running Scenario 5: Stopped Instance Recovery"
    
    check_k6_installed
    check_environment
    
    local num_users="${NUM_USERS:-10}"
    local pool_size="${INSTANCE_POOL_SIZE:-${num_users}}"
    
    print_info "Configuration:"
    print_info "  Users: $num_users"
    print_info "  Instance Pool Size: $pool_size"
    print_info "  Test: Stop instances and verify automatic start"
    
    # Check if instances are available
    print_info "\n🔍 Checking instance pool status..."
    if ! check_instance_pool "$pool_size"; then
        print_warning "Instance pool may not be ready"
        print_info "Would you like to prepare instances now? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            prepare_instances "$pool_size" "pool"
            if [ $? -eq 0 ]; then
                print_info "Waiting 1 min for instances to initialize..."
                sleep 60
            fi
        fi
    fi
    
    local output_file="scenario5_results_$(date +%Y%m%d_%H%M%S).txt"
    print_info "\nRunning test... (output will be saved to $output_file)"
    print_warning "⚠️  Note: This test requires the Lambda function to have the stopped instance auto-start fix deployed."
    print_info "   If metrics show 0% detection/success, the Lambda code needs to be updated and deployed."
    
    # Use test's internal scenarios configuration (shared-iterations) instead of CLI flags
    # This allows the test to properly control iterations per user
    k6 run \
        -e "USER_MANAGEMENT_URL=$USER_MANAGEMENT_URL" \
        -e "INSTANCE_MANAGER_URL=$INSTANCE_MANAGER_URL" \
        -e "INSTANCE_MANAGER_PASSWORD=$INSTANCE_MANAGER_PASSWORD" \
        -e "NUM_USERS=$num_users" \
        -e "INSTANCE_POOL_SIZE=$pool_size" \
        k6_scenario5_stopped_instance_recovery.js \
        | tee "$output_file"
    
    local exit_code=${PIPESTATUS[0]}
    if [ $exit_code -eq 0 ]; then
        # Check if business logic passed by looking at the output
        if grep -q "Business Logic: PASSED" "$output_file"; then
            print_success "Scenario 5 completed successfully - Business logic validated"
        elif grep -q "Business Logic: PARTIAL" "$output_file"; then
            print_warning "Scenario 5 completed but business logic validation was PARTIAL"
            print_info "Check the metrics in the output file for details"
        else
            print_warning "Scenario 5 completed but business logic validation status unclear"
        fi
        print_info "Results saved to: $output_file"
    else
        print_error "Scenario 5 failed with exit code $exit_code"
        exit 1
    fi
}

run_all() {
    print_header "Running All Test Scenarios"
    
    print_info "This will run all 5 scenarios:"
    print_info "  1. New User Instance Assignment"
    print_info "  2. User Instance Persistence"
    print_info "  3. Instance Termination and Reassignment"
    print_info "  4. Pool Exhaustion and Recovery"
    print_info "  5. Stopped Instance Recovery"
    print_warning "Make sure you have enough instances in the pool!"
    
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled"
        exit 0
    fi
    
    # Run all scenarios
    run_scenario1
    echo ""; sleep 2
    
    run_scenario2
    echo ""; sleep 2
    
    run_scenario3
    echo ""; sleep 2
    
    run_scenario4
    echo ""; sleep 2
    
    run_scenario5
    
    print_success "All scenarios completed!"
}

show_help() {
    cat << EOF
k6 Test Runner Script

Usage:
    ./run_k6_tests.sh [command] [options]

Commands:
    prepare [--count N]     Prepare instance pool (default: 20 instances)
    scenario1              Run Scenario 1: New User Instance Assignment
    scenario2              Run Scenario 2: User Instance Persistence
    scenario3              Run Scenario 3: Instance Termination and Reassignment
    scenario4              Run Scenario 4: Pool Exhaustion and Recovery
    scenario5              Run Scenario 5: Stopped Instance Recovery
    all                    Run all scenarios (1-5)
    help                   Show this help message

Environment Variables:
    USER_MANAGEMENT_URL       (required) User Management Lambda URL
    INSTANCE_MANAGER_URL      (required) Instance Manager Lambda URL
    INSTANCE_MANAGER_PASSWORD (optional) Instance Manager password
    
    INSTANCE_POOL_SIZE        (optional) Pool size for both scenarios
                                - Scenario 1: default 20, must match expected users
                                - Scenario 2: default NUM_USERS, must be >= NUM_USERS
    
    NUM_USERS                 (optional) Number of users for Scenario 2 (default: 10)
    REFRESHES_PER_USER        (optional) Refreshes per user for Scenario 2 (default: 10)
    
    INSTANCE_COUNT            (optional) Legacy: Number of instances (default: 20)
                                Note: Use INSTANCE_POOL_SIZE instead

Examples:
    # Prepare 20 instances
    ./run_k6_tests.sh prepare --count 20

    # Run Scenario 1 with 20 instances (default)
    export USER_MANAGEMENT_URL="https://..."
    export INSTANCE_MANAGER_URL="https://..."
    ./run_k6_tests.sh scenario1

    # Run Scenario 1 with 40 instances
    export INSTANCE_POOL_SIZE=40
    ./run_k6_tests.sh scenario1

    # Run Scenario 2 with 10 users (default)
    ./run_k6_tests.sh scenario2

    # Run Scenario 2 with 20 users and 20 instances
    export NUM_USERS=20
    export INSTANCE_POOL_SIZE=20
    ./run_k6_tests.sh scenario2

    # Run Scenario 2 with 10 users but 30 instances (larger pool)
    export NUM_USERS=10
    export INSTANCE_POOL_SIZE=30
    ./run_k6_tests.sh scenario2

    # Run Scenario 3: Instance Termination and Reassignment
    ./run_k6_tests.sh scenario3

    # Run Scenario 4: Pool Exhaustion (15 users, 10 instances)
    export NUM_USERS=15
    export INSTANCE_POOL_SIZE=10
    ./run_k6_tests.sh scenario4

    # Run Scenario 5: Stopped Instance Recovery
    ./run_k6_tests.sh scenario5

    # Run all scenarios
    ./run_k6_tests.sh all
EOF
}

# Main script
case "${1:-help}" in
    prepare)
        check_environment
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --count)
                    INSTANCE_COUNT="$2"
                    shift 2
                    ;;
                --type)
                    INSTANCE_TYPE="$2"
                    shift 2
                    ;;
                *)
                    print_error "Unknown option: $1"
                    show_help
                    exit 1
                    ;;
            esac
        done
        prepare_instances "$INSTANCE_COUNT" "$INSTANCE_TYPE"
        ;;
    scenario1)
        run_scenario1
        ;;
    scenario2)
        run_scenario2
        ;;
    scenario3)
        run_scenario3
        ;;
    scenario4)
        run_scenario4
        ;;
    scenario5)
        run_scenario5
        ;;
    all)
        run_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

