# Tests

Automated test suite for the Docker All-in-One infrastructure scripts using [bats-core](https://github.com/bats-core/bats-core).

## Structure

```
tests/
├── libs/                    # Vendored test dependencies
│   ├── bats-core/          # bats test runner
│   │   └── bin/bats        # bats executable
│   ├── bats-support/       # Helper library for test formatting
│   │   └── load.bash
│   └── bats-assert/        # Assertion functions (assert_success, etc.)
│       └── load.bash
├── smoke_test.bats          # Framework smoke test
├── run_tests.sh            # Test suite runner
└── README.md               # This file
```

## Running Tests

Run the full test suite:

```bash
./tests/run_tests.sh
```

Run with TAP output format:

```bash
./tests/run_tests.sh --tap
```

Run a specific test file:

```bash
./tests/run_tests.sh tests/smoke_test.bats
```

Run bats directly:

```bash
./tests/libs/bats-core/bin/bats --pretty tests/smoke_test.bats
```

## Writing Tests

Create `.bats` files in the `tests/` directory. Each test file should:

1. Load the support and assert libraries
2. Define tests with the `@test` annotation

```bash
#!/usr/bin/env bats

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

@test "description of what is being tested" {
    run some_command --with-args
    assert_success
    assert_output --partial "expected substring"
}
```

## Available Assertions

- `assert_success` - command exited with status 0
- `assert_failure [code]` - command exited with non-zero (optionally specific code)
- `assert_output "exact"` - output matches exactly
- `assert_output --partial "sub"` - output contains substring
- `assert_output --regexp "pat"` - output matches regex
- `refute_output "string"` - output does not match
- `refute_output --partial "sub"` - output does not contain
- `assert_line "line"` - a line exists in output
- `assert_line --index N "line"` - specific line at index matches
- `assert_line --partial "sub"` - a line contains substring
- `refute_line "line"` - no line matches
- `assert_equal "expected" "actual"` - two values are equal
- `assert_not_equal "a" "b"` - two values differ

## Requirements

- Bash 4.0+ (for associative arrays and regex matching)
- Standard POSIX utilities (grep, sed, find, mktemp)
