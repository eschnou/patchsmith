# Manual Testing Guide

This guide helps you test Patchsmith components with real external tools (CodeQL, Git, Claude API).

## Prerequisites

Before running manual tests, ensure you have:

1. **CodeQL CLI** installed and in PATH
   - Download from: https://github.com/github/codeql-cli-binaries/releases
   - Extract and add to PATH
   - Verify: `codeql version`

2. **Git** installed
   - Should already be available on most systems
   - Verify: `git --version`

3. **Claude API Key** (for AI agent tests)
   - Set environment variable: `export ANTHROPIC_API_KEY=your-key`

## Testing CodeQL Integration

### Quick Test

Run the automated integration test:

```bash
# From project root
python tests/manual_test_codeql.py
```

This will:
- ✅ Verify CodeQL is installed
- ✅ Create a sample Python project
- ✅ Create a CodeQL database
- ✅ Test overwrite behavior
- ✅ Test error handling

Expected output:
```
🧪 MANUAL CODEQL INTEGRATION TEST
============================================================

TEST 1: CodeQL Version Detection
============================================================
✅ SUCCESS: CodeQL version 2.15.3 detected

TEST 2: Database Creation
============================================================
📁 Creating sample Python project...
📊 Creating CodeQL database...
✅ SUCCESS: Database created!

TEST 3: Database Overwrite
============================================================
✅ Database overwritten successfully

TEST 4: Error Handling
============================================================
✅ Correctly raised errors for invalid inputs

🎉 ALL TESTS PASSED!
```

### Manual CLI Test (Alternative)

Test the CodeQL adapter directly from Python:

```bash
poetry shell
python
```

```python
from pathlib import Path
from patchsmith.adapters.codeql.cli import CodeQLCLI

# Initialize
cli = CodeQLCLI()
print(f"CodeQL version: {cli.get_version()}")

# Create a test project (prepare some Python code first)
project_dir = Path("/path/to/your/test/project")
db_path = Path("/tmp/test-db")

# Create database
cli.create_database(
    source_root=project_dir,
    db_path=db_path,
    language="python"
)

# Check if database exists
print(f"Database exists: {cli.check_database_exists(db_path)}")
```

## Troubleshooting

### "CodeQL CLI not found"

Make sure CodeQL is in your PATH:

```bash
# Check if CodeQL is available
which codeql

# If not found, download and add to PATH
# macOS/Linux:
export PATH="/path/to/codeql:$PATH"

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export PATH="/path/to/codeql:$PATH"' >> ~/.zshrc
```

### "Database creation failed"

Common causes:
- Source directory doesn't contain valid code
- Language specified doesn't match source code
- Insufficient permissions
- CodeQL version incompatibility

Check CodeQL logs for details:
```bash
codeql database create --help
```

## Testing Git Integration

Git adapter tests coming in Phase 2, Task 25-27.

## Testing Claude AI Integration

Claude AI agent tests coming in Phase 2, Task 19-24.

## Unit Tests vs Manual Tests

**Unit tests** (mock external dependencies):
```bash
poetry run pytest tests/unit/
```

**Manual tests** (use real external tools):
```bash
python tests/manual_test_codeql.py
```

Use manual tests to verify:
- Real CodeQL CLI integration works
- Database creation on actual projects
- Error messages are helpful
- Performance is acceptable

Unit tests verify:
- Logic correctness
- Error handling
- Edge cases
- Code coverage
