# Integration Tests

This directory contains end-to-end integration tests that validate that all Patchsmith adapters work together correctly.

## Requirements

Integration tests require real external tools and services:

1. **CodeQL CLI**: Must be installed and available in PATH
   ```bash
   # Check if CodeQL is installed
   codeql --version
   ```

2. **Anthropic API Key**: Set the environment variable
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

3. **Git**: Required for repository operations
   ```bash
   git --version
   ```

4. **GitHub CLI (optional)**: For PR creation tests
   ```bash
   gh --version
   gh auth status
   ```

## Running Integration Tests

### Run all integration tests:
```bash
poetry run pytest tests/integration/ -v -m integration
```

### Run specific test:
```bash
poetry run pytest tests/integration/test_e2e_workflow.py::TestE2EWorkflow::test_complete_workflow -v -s
```

### Run with a custom project (recommended for testing with real code):
```bash
# Test on a real codebase instead of the generated test project
TEST_PROJECT_PATH=/path/to/your/project poetry run pytest tests/integration/test_e2e_workflow.py::TestE2EWorkflow::test_complete_workflow -v -s
```

### Run with output visible (recommended for seeing the workflow):
```bash
poetry run pytest tests/integration/ -v -s -m integration
```

### Skip integration tests during normal testing:
```bash
# This will skip integration tests (they're marked with @pytest.mark.integration)
poetry run pytest tests/unit/ -v
```

## What the E2E Test Does

The `test_e2e_workflow.py` test validates the complete Patchsmith workflow:

1. **Language Detection**: Uses Claude AI to detect languages in a test project
2. **CodeQL Database Creation**: Creates a CodeQL database for Python
3. **Query Execution**: Runs standard security queries
4. **Result Parsing**: Parses SARIF output to Finding objects
5. **False Positive Filtering**: Uses Claude AI to analyze findings
6. **Report Generation**: Generates a markdown security report
7. **Fix Generation**: Uses Claude AI to generate code fixes
8. **Git Operations**: Creates a branch and commits the fix
9. **PR Creation**: (Optional) Creates a pull request using GitHub CLI

## Expected Behavior

### Default Test Project
- By default, the test creates a temporary test project with a known SQL injection vulnerability
- It runs the complete workflow and validates each step
- The test may exit early if CodeQL doesn't detect findings (the test code is intentionally simple)
- All console output is printed to help understand what's happening at each stage

### Custom Project (via TEST_PROJECT_PATH)
- When you provide a real project path, the test will analyze that codebase instead
- The test will use the existing git repository (no initialization)
- More likely to find real vulnerabilities with CodeQL's standard queries
- Recommended for validating the complete workflow with actual findings

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Set your API key:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "CodeQL CLI not found"
Install CodeQL from: https://github.com/github/codeql-cli-binaries/releases

Add to PATH:
```bash
export PATH="/path/to/codeql:$PATH"
```

### Test times out
Integration tests can take several minutes due to:
- CodeQL database creation (~30-60s)
- Multiple Claude API calls (~5-10s each)
- Git operations

Use the `-s` flag to see progress output.

### GitHub CLI errors
PR creation tests are optional. If `gh` is not installed or not authenticated, those steps will be skipped with warnings.

### "No findings detected by CodeQL"
This can happen with the default test project because:
- The test code is intentionally simple
- CodeQL's standard queries may not trigger on basic patterns
- The test will exit gracefully if no findings are detected

**Solution**: Run the test on a real codebase:
```bash
TEST_PROJECT_PATH=/path/to/real/project poetry run pytest tests/integration/test_e2e_workflow.py::TestE2EWorkflow::test_complete_workflow -v -s
```

### CodeQL query pack errors
The test automatically downloads CodeQL query packs if they're not available. If you get errors:
```bash
# Pre-download Python security queries
codeql pack download codeql/python-queries
```

## Notes

- Integration tests are **NOT run by default** in CI/CD
- They consume API credits (Claude API)
- They require internet connectivity
- They may take 2-5 minutes to complete
- They validate real-world workflow, not just unit test mocks
- Use `TEST_PROJECT_PATH` environment variable to test on real codebases
- The test exits gracefully if no findings are detected (no mock data injected)
