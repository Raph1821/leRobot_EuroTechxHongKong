#!/usr/bin/env bash
# bats-support - Supporting library for bats-core test helpers
# Vendored minimal implementation
# Based on bats-support (https://github.com/bats-core/bats-support)
# License: CC0-1.0

# Output formatting helpers

# Print a formatted error message for assertion failures
batslib_print_kv_single() {
    local -ir col_width="$1"
    shift
    while [[ $# -gt 1 ]]; do
        local key="$1"
        local value="$2"
        shift 2
        printf "%-${col_width}s : %s\n" "$key" "$value"
    done
}

batslib_print_kv_multi() {
    while [[ $# -gt 1 ]]; do
        local key="$1"
        local value="$2"
        shift 2
        printf "%s (%d lines):\n" "$key" "$(echo "$value" | wc -l)"
        printf "%s\n" "$value" | sed 's/^/  | /'
    done
}

batslib_print_kv_single_or_multi() {
    local -ir width="$1"
    shift
    local -a pairs=("$@")

    local has_multi=0
    local i=1
    while [[ $i -lt ${#pairs[@]} ]]; do
        if [[ "${pairs[$i]}" == *$'\n'* ]]; then
            has_multi=1
            break
        fi
        i=$((i + 2))
    done

    if [[ $has_multi -eq 1 ]]; then
        batslib_print_kv_multi "${pairs[@]}"
    else
        batslib_print_kv_single "$width" "${pairs[@]}"
    fi
}

# Prefix each line of input with a given string
batslib_prefix() {
    local prefix="${1:- }"
    local line
    while IFS= read -r line; do
        printf "%s%s\n" "$prefix" "$line"
    done
}

# Mark the differences between expected and actual output
batslib_mark() {
    local -r symbol="$1"
    local line
    while IFS= read -r line; do
        printf "%s %s\n" "$symbol" "$line"
    done
}

# Decorate output with a header
batslib_decorate() {
    local -r header="$1"
    echo ""
    echo "-- $header --"
    cat
    echo "--"
    echo ""
}

# Check if a command is available
batslib_is_caller() {
    local -i depth="$1"
    local caller="${FUNCNAME[$((depth + 2))]}"
    [[ "$caller" == "$2" ]]
}

# Get the count of lines in a string
batslib_count_lines() {
    local -i count=0
    while IFS= read -r _; do
        count=$((count + 1))
    done <<< "$1"
    echo "$count"
}
