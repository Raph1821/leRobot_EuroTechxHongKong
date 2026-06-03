#!/usr/bin/env bash
# bats-assert - Assertion library for bats-core
# Vendored minimal implementation
# Based on bats-assert (https://github.com/bats-core/bats-assert)
# License: CC0-1.0

# Load bats-support dependency
BATS_ASSERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${BATS_ASSERT_DIR}/../bats-support/load.bash" ]]; then
    source "${BATS_ASSERT_DIR}/../bats-support/load.bash"
fi

# assert_success
# Asserts that the most recent `run` command exited with status 0
assert_success() {
    if [[ "$status" -ne 0 ]]; then
        {
            echo "-- command failed --"
            echo "status : $status"
            if [[ -n "${output:-}" ]]; then
                echo "output : $output"
            fi
            echo "--"
        } | batslib_decorate "assert_success" >&2
        return 1
    fi
}

# assert_failure
# Asserts that the most recent `run` command exited with a non-zero status
# Optionally checks for a specific exit code: assert_failure 2
assert_failure() {
    local expected_status="${1:-}"

    if [[ -n "$expected_status" ]]; then
        if [[ "$status" -ne "$expected_status" ]]; then
            {
                echo "-- command exit code mismatch --"
                echo "expected : $expected_status"
                echo "actual   : $status"
                echo "--"
            } >&2
            return 1
        fi
    else
        if [[ "$status" -eq 0 ]]; then
            {
                echo "-- command succeeded, but failure expected --"
                if [[ -n "${output:-}" ]]; then
                    echo "output : $output"
                fi
                echo "--"
            } | batslib_decorate "assert_failure" >&2
            return 1
        fi
    fi
}

# assert_output
# Asserts that the output of the most recent `run` command matches expected
# Usage:
#   assert_output "expected string"        # exact match
#   assert_output --partial "substring"    # partial match
#   assert_output --regexp "pattern"       # regex match
assert_output() {
    local partial=0
    local regexp=0
    local expected=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --partial|-p)
                partial=1
                shift
                ;;
            --regexp|-e)
                regexp=1
                shift
                ;;
            --)
                shift
                expected="$1"
                shift
                ;;
            *)
                expected="$1"
                shift
                ;;
        esac
    done

    if [[ $partial -eq 1 ]]; then
        if [[ "${output}" != *"${expected}"* ]]; then
            {
                echo "-- output does not contain substring --"
                echo "substring : $expected"
                echo "output    : $output"
                echo "--"
            } >&2
            return 1
        fi
    elif [[ $regexp -eq 1 ]]; then
        if ! [[ "${output}" =~ ${expected} ]]; then
            {
                echo "-- output does not match regexp --"
                echo "pattern : $expected"
                echo "output  : $output"
                echo "--"
            } >&2
            return 1
        fi
    else
        if [[ "${output}" != "${expected}" ]]; then
            {
                echo "-- output differs --"
                echo "expected : $expected"
                echo "actual   : $output"
                echo "--"
            } >&2
            return 1
        fi
    fi
}

# refute_output
# Asserts that the output does NOT match
# Usage:
#   refute_output "string"               # not exact match
#   refute_output --partial "substring"  # does not contain
#   refute_output --regexp "pattern"     # does not match regex
#   refute_output                        # output is empty
refute_output() {
    local partial=0
    local regexp=0
    local unexpected=""

    if [[ $# -eq 0 ]]; then
        # No arguments: assert output is empty
        if [[ -n "${output:-}" ]]; then
            {
                echo "-- output is not empty --"
                echo "output : $output"
                echo "--"
            } >&2
            return 1
        fi
        return 0
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --partial|-p)
                partial=1
                shift
                ;;
            --regexp|-e)
                regexp=1
                shift
                ;;
            --)
                shift
                unexpected="$1"
                shift
                ;;
            *)
                unexpected="$1"
                shift
                ;;
        esac
    done

    if [[ $partial -eq 1 ]]; then
        if [[ "${output}" == *"${unexpected}"* ]]; then
            {
                echo "-- output should not contain substring --"
                echo "substring : $unexpected"
                echo "output    : $output"
                echo "--"
            } >&2
            return 1
        fi
    elif [[ $regexp -eq 1 ]]; then
        if [[ "${output}" =~ ${unexpected} ]]; then
            {
                echo "-- output should not match regexp --"
                echo "pattern : $unexpected"
                echo "output  : $output"
                echo "--"
            } >&2
            return 1
        fi
    else
        if [[ "${output}" == "${unexpected}" ]]; then
            {
                echo "-- output equals, but it was not expected --"
                echo "output : $output"
                echo "--"
            } >&2
            return 1
        fi
    fi
}

# assert_line
# Asserts that a specific line exists in the output
# Usage:
#   assert_line "expected line"                  # line exists anywhere
#   assert_line --index 0 "expected first line"  # specific line index
#   assert_line --partial "substring"            # line containing substring
assert_line() {
    local index=""
    local partial=0
    local regexp=0
    local expected=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --index|-n)
                shift
                index="$1"
                shift
                ;;
            --partial|-p)
                partial=1
                shift
                ;;
            --regexp|-e)
                regexp=1
                shift
                ;;
            --)
                shift
                expected="$1"
                shift
                ;;
            *)
                expected="$1"
                shift
                ;;
        esac
    done

    if [[ -n "$index" ]]; then
        # Check specific line by index
        local actual_line="${lines[$index]:-}"
        if [[ $partial -eq 1 ]]; then
            if [[ "${actual_line}" != *"${expected}"* ]]; then
                {
                    echo "-- line ${index} does not contain substring --"
                    echo "substring : $expected"
                    echo "line      : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        elif [[ $regexp -eq 1 ]]; then
            if ! [[ "${actual_line}" =~ ${expected} ]]; then
                {
                    echo "-- line ${index} does not match regexp --"
                    echo "pattern : $expected"
                    echo "line    : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        else
            if [[ "${actual_line}" != "${expected}" ]]; then
                {
                    echo "-- line ${index} differs --"
                    echo "expected : $expected"
                    echo "actual   : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        fi
    else
        # Search all lines
        local found=0
        local line
        for line in "${lines[@]}"; do
            if [[ $partial -eq 1 ]]; then
                if [[ "${line}" == *"${expected}"* ]]; then
                    found=1
                    break
                fi
            elif [[ $regexp -eq 1 ]]; then
                if [[ "${line}" =~ ${expected} ]]; then
                    found=1
                    break
                fi
            else
                if [[ "${line}" == "${expected}" ]]; then
                    found=1
                    break
                fi
            fi
        done

        if [[ $found -eq 0 ]]; then
            {
                echo "-- line not found --"
                echo "expected : $expected"
                echo "output (${#lines[@]} lines):"
                local i
                for i in "${!lines[@]}"; do
                    echo "  [$i] : ${lines[$i]}"
                done
                echo "--"
            } >&2
            return 1
        fi
    fi
}

# refute_line
# Asserts that a line does NOT exist in the output
# Usage:
#   refute_line "unexpected line"
#   refute_line --partial "substring"
#   refute_line --index 0 "unexpected first line"
refute_line() {
    local index=""
    local partial=0
    local regexp=0
    local unexpected=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --index|-n)
                shift
                index="$1"
                shift
                ;;
            --partial|-p)
                partial=1
                shift
                ;;
            --regexp|-e)
                regexp=1
                shift
                ;;
            --)
                shift
                unexpected="$1"
                shift
                ;;
            *)
                unexpected="$1"
                shift
                ;;
        esac
    done

    if [[ -n "$index" ]]; then
        local actual_line="${lines[$index]:-}"
        if [[ $partial -eq 1 ]]; then
            if [[ "${actual_line}" == *"${unexpected}"* ]]; then
                {
                    echo "-- line ${index} should not contain substring --"
                    echo "substring : $unexpected"
                    echo "line      : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        elif [[ $regexp -eq 1 ]]; then
            if [[ "${actual_line}" =~ ${unexpected} ]]; then
                {
                    echo "-- line ${index} should not match regexp --"
                    echo "pattern : $unexpected"
                    echo "line    : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        else
            if [[ "${actual_line}" == "${unexpected}" ]]; then
                {
                    echo "-- line ${index} should differ --"
                    echo "actual : $actual_line"
                    echo "--"
                } >&2
                return 1
            fi
        fi
    else
        local line
        for line in "${lines[@]}"; do
            if [[ $partial -eq 1 ]]; then
                if [[ "${line}" == *"${unexpected}"* ]]; then
                    {
                        echo "-- line should not be found --"
                        echo "line : $line"
                        echo "--"
                    } >&2
                    return 1
                fi
            elif [[ $regexp -eq 1 ]]; then
                if [[ "${line}" =~ ${unexpected} ]]; then
                    {
                        echo "-- line should not match regexp --"
                        echo "pattern : $unexpected"
                        echo "line    : $line"
                        echo "--"
                    } >&2
                    return 1
                fi
            else
                if [[ "${line}" == "${unexpected}" ]]; then
                    {
                        echo "-- line should not exist --"
                        echo "line : $line"
                        echo "--"
                    } >&2
                    return 1
                fi
            fi
        done
    fi
}

# assert_equal
# Asserts two values are equal
assert_equal() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" != "$actual" ]]; then
        {
            echo "-- values are not equal --"
            echo "expected : $expected"
            echo "actual   : $actual"
            echo "--"
        } >&2
        return 1
    fi
}

# assert_not_equal
# Asserts two values are not equal
assert_not_equal() {
    local unexpected="$1"
    local actual="$2"
    if [[ "$unexpected" == "$actual" ]]; then
        {
            echo "-- values should not be equal --"
            echo "value : $actual"
            echo "--"
        } >&2
        return 1
    fi
}

# assert
# Asserts that a command exits successfully
assert() {
    if ! "$@"; then
        {
            echo "-- assertion failed --"
            echo "command : $*"
            echo "--"
        } >&2
        return 1
    fi
}

# refute
# Asserts that a command exits with failure
refute() {
    if "$@"; then
        {
            echo "-- assertion should have failed --"
            echo "command : $*"
            echo "--"
        } >&2
        return 1
    fi
}
