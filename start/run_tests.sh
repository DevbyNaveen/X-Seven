#!/bin/bash

# X-Seven Backend Testing Suite Runner
# This script runs all tests and generates a consolidated report

echo "===================================="
echo "X-Seven Backend Testing Suite"
echo "===================================="
echo

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found"
    echo "Please create a virtual environment with 'python -m venv .venv'"
    exit 1
fi

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to run a test and report result
run_test() {
    local test_file=$1
    local test_name=$2
    
    echo -e "\n${YELLOW}Running $test_name...${NC}"
    python $test_file
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $test_name PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_name FAILED${NC}"
        return 1
    fi
}

# Create test results directory
mkdir -p test_results

# Run all tests
echo "Starting tests at $(date)"

# Track results
total_tests=0
passed_tests=0

# Database Tests
total_tests=$((total_tests+1))
run_test test_database.py "Database Connectivity"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# Redis Tests
total_tests=$((total_tests+1))
run_test test_redis.py "Redis Integration"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# Kafka Tests
total_tests=$((total_tests+1))
run_test test_kafka.py "Kafka Messaging"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# Temporal Tests
total_tests=$((total_tests+1))
run_test test_temporal.py "Temporal Workflow System"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# DSPy Tests
total_tests=$((total_tests+1))
run_test test_dspy.py "DSPy Integration"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# Service Mesh Tests
total_tests=$((total_tests+1))
run_test test_service_mesh.py "Service Mesh Initialization"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# End-to-end Tests
total_tests=$((total_tests+1))
run_test test_end_to_end.py "End-to-End Workflow"
if [ $? -eq 0 ]; then
    passed_tests=$((passed_tests+1))
fi

# Print summary
echo -e "\n===================================="
echo "Test Summary"
echo "===================================="
echo -e "Total tests: $total_tests"
echo -e "Passed tests: ${GREEN}$passed_tests${NC}"
echo -e "Failed tests: ${RED}$((total_tests - passed_tests))${NC}"

if [ $passed_tests -eq $total_tests ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. See test output for details.${NC}"
    echo -e "\nSee full report in TEST_REPORT.md"
    exit 1
fi
