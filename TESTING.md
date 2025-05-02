# Testing Strategy for IntuitiveDirTree

This document outlines the testing approach for the IntuitiveDirTree project, explaining the test structure, coverage goals, and how to run tests.

## Test Structure

The test suite is organized into several categories:

1. **Core Functionality Tests** (`test_tree_generation.py`)
   - Tests the basic tree generation functionality
   - Verifies that filtering options work correctly
   - Tests display options like depth limits, styles, and size display

2. **Filtering Logic Tests** (`test_filtering_logic.py`)
   - Tests the pattern matching and filtering logic in detail
   - Verifies include/exclude patterns work correctly
   - Tests directory recursion decisions

3. **LLM Export Tests** (`test_llm_export.py`)
   - Tests the LLM export functionality
   - Verifies content inclusion/exclusion
   - Tests file size limits and content formatting

4. **CLI Tests** (`test_cli.py`)
   - Tests command-line argument parsing
   - Verifies CLI options are correctly interpreted

5. **Edge Case Tests** (`test_edge_cases.py`)
   - Tests complex pattern interactions
   - Tests error handling scenarios
   - Tests binary file detection and encoding issues
   - Tests path normalization across different formats

## Running Tests

To run the full test suite:

```bash
python -m pytest
```

To run a specific test file:

```bash
python -m pytest tests/test_edge_cases.py
```

To run tests with verbose output:

```bash
python -m pytest -v
```

## Test Fixtures

The tests use several fixtures defined in `conftest.py`:

- `base_test_structure`: Creates a standard directory structure for testing
- `filter_test_structure`: Creates a structure specifically for testing filtering
- `run_dirtree_and_capture`: Helper to run the tree generator and capture output

## Coverage Goals

The test suite aims to cover:

1. **Functional Coverage**: All features and options should be tested
2. **Edge Case Coverage**: Unusual inputs and error conditions should be tested
3. **User Scenario Coverage**: Common user workflows should be tested

## Adding New Tests

When adding new features, follow these guidelines for testing:

1. Add tests for the happy path (normal operation)
2. Add tests for edge cases and error conditions
3. Consider user scenarios that might lead to unexpected results
4. For UI/CLI changes, test both the parsing and execution paths

## Continuous Improvement

The testing strategy evolves with the project. Areas for improvement include:

1. Adding performance tests for large directory structures
2. Improving test coverage for interactive features
3. Adding more comprehensive error handling tests
4. Testing with various file systems and operating systems
