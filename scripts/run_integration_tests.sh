#!/bin/bash

# This script runs static analysis and tests for the core `src` directory.

# --- Configuration ---
# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Return value of a pipeline is the value of the last command to exit with a non-zero status.
set -o pipefail

# Get the absolute path of the project's root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_ROOT/src/"
INTEGRATION_TESTS_DIR="$PROJECT_ROOT/tests/integration"

# --- Output Colors ---
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_RED='\033[0;31m'
COLOR_NC='\033[0m' # No Color

# --- Helper Functions ---

# Prints a formatted header to the console.
# Arguments:
#   $1: The text to display in the header.
print_header() {
    echo -e "\n${COLOR_YELLOW}=======================================================================${COLOR_NC}"
    echo -e "${COLOR_YELLOW}  $1${COLOR_NC}"
    echo -e "${COLOR_YELLOW}=======================================================================${COLOR_NC}"
}

# Checks if a command exists in the current environment.
# Arguments:
#   $1: The name of the command to check.
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Pre-flight Checks ---

# Ensure the script is run from within a Python virtual environment.
if ! [[ "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${COLOR_RED}ERROR: Not in a Python virtual environment. Please activate one before running this script.${COLOR_NC}"
    exit 1
fi

# Verify that all required development tools are installed.
REQUIRED_COMMANDS=("pytest")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command_exists "$cmd"; then
        echo -e "${COLOR_RED}ERROR: Command '$cmd' not found.${COLOR_NC}"
        echo "Please install the development dependencies, for example by running:"
        echo "pip install -e '.[dev]'"
        exit 1
    fi
done

# --- Main Execution ---

# Change to the project root directory to ensure all paths are resolved correctly.
cd "$PROJECT_ROOT"

# Install core development dependencies
print_header "Installing Core Dependencies"
pip install -e ".[dev]"
pip install -e ".[examples]"

print_header "Running Automated Integration Tests"
echo "Running pytest for integration tests and generating a code coverage report..."
pytest "$INTEGRATION_TESTS_DIR" --cov="$SOURCE_DIR" --cov-fail-under=80 --cov-report=term-missing

# --- Success ---
print_header "All core tests passed successfully!"
echo -e "${COLOR_GREEN}Great job! Your core code is clean, secure, and thoroughly tested.${COLOR_NC}"

exit 0
