#!/usr/bin/env bash
# run_tests.sh - Execute the full bats test suite
# Usage: ./tests/run_tests.sh [--pretty] [test-file.bats ...]
#
# Runs all .bats test files in the tests/ directory using the vendored
# bats-core framework. Supports TAP output (default) or pretty formatting.

set -euo pipefail

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BATS_BIN="${SCRIPT_DIR}/libs/bats-core/bin/bats"

# Ensure bats is executable
chmod +x "$BATS_BIN"

# Parse arguments
FORMAT="--pretty"
BATS_FILES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tap)
            FORMAT="--tap"
            shift
            ;;
        --pretty)
            FORMAT="--pretty"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--pretty|--tap] [test-file.bats ...]"
            echo ""
            echo "Options:"
            echo "  --pretty   Use colored pretty output (default)"
            echo "  --tap      Use TAP output format"
            echo ""
            echo "If no test files are specified, all .bats files in tests/ are run."
            exit 0
            ;;
        *)
            BATS_FILES+=("$1")
            shift
            ;;
    esac
done

# If no specific files given, find all .bats files
if [[ ${#BATS_FILES[@]} -eq 0 ]]; then
    while IFS= read -r -d '' file; do
        BATS_FILES+=("$file")
    done < <(find "$SCRIPT_DIR" -name "*.bats" -not -path "*/libs/*" -print0 | sort -z)
fi

if [[ ${#BATS_FILES[@]} -eq 0 ]]; then
    echo "No .bats test files found in ${SCRIPT_DIR}/"
    echo "Create test files with the .bats extension to get started."
    exit 0
fi

echo "============================================"
echo "  Running bats test suite"
echo "  Tests: ${#BATS_FILES[@]} file(s)"
echo "============================================"

# Run bats
"$BATS_BIN" "$FORMAT" "${BATS_FILES[@]}"
exit_code=$?

echo ""
if [[ $exit_code -eq 0 ]]; then
    echo "All tests passed!"
else
    echo "Some tests failed. Exit code: $exit_code"
fi

exit $exit_code
