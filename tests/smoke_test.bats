#!/usr/bin/env bats
# Smoke test to verify the bats testing framework is functional

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

@test "bats framework loads successfully" {
    run echo "hello bats"
    assert_success
    assert_output "hello bats"
}

@test "assert_failure detects non-zero exit" {
    run false
    assert_failure
}

@test "assert_output --partial matches substrings" {
    run echo "hello world from bats"
    assert_success
    assert_output --partial "world"
}

@test "assert_line finds specific lines in output" {
    run printf "line1\nline2\nline3"
    assert_success
    assert_line "line2"
}

@test "refute_output --partial rejects missing substrings" {
    run echo "hello world"
    assert_success
    refute_output --partial "foobar"
}
