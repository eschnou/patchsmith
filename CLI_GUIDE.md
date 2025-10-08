# Patchsmith CLI Guide

Welcome to Patchsmith! This guide will help you get started with the CLI.

## Prerequisites

1. **Install Patchsmith**:
   ```bash
   poetry install
   ```

2. **Set up API Key** (required for AI features):
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

   Or add to your shell profile:
   ```bash
   echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.zshrc  # or ~/.bashrc
   source ~/.zshrc
   ```

3. **Install CodeQL** (required for analysis):
   - Download from: https://github.com/github/codeql-cli-binaries/releases
   - Ensure `codeql` is in your PATH

## Quick Start

### 1. Initialize a Project

```bash
patchsmith init /path/to/your/project
```

This creates a `.patchsmith` directory with configuration.

### 2. Run Security Analysis

```bash
cd /path/to/your/project
patchsmith analyze
```

Or analyze a specific path:
```bash
patchsmith analyze ~/code/my-app
```

The analysis performs:
- **Language Detection** - Identifies programming languages
- **CodeQL Analysis** - Runs static security analysis
- **AI Triage** - Prioritizes findings by severity and exploitability
- **Detailed Assessment** - Deep security analysis on top issues

### 3. Generate Report

```bash
patchsmith report
```

Options:
```bash
patchsmith report --format html        # HTML report
patchsmith report -o my_report.md      # Custom output path
```

### 4. Fix Vulnerabilities

Interactive mode (recommended):
```bash
patchsmith fix --interactive
```

Fix specific finding:
```bash
patchsmith fix <finding-id>
```

Auto-apply fix:
```bash
patchsmith fix <finding-id> --apply
```

## Commands Reference

### `patchsmith analyze`

Run complete security analysis on a project.

**Usage:**
```bash
patchsmith analyze [PATH] [OPTIONS]
```

**Options:**
- `--triage / --no-triage` - Enable/disable AI triage (default: on)
- `--detailed / --no-detailed` - Enable/disable detailed analysis (default: on)
- `--detailed-limit INTEGER` - Max findings for detailed analysis (default: 5)
- `-o, --output PATH` - Save results to JSON file

**Examples:**
```bash
# Analyze current directory
patchsmith analyze

# Analyze specific project
patchsmith analyze ~/code/my-app

# Skip triage for faster analysis
patchsmith analyze --no-triage

# Analyze more findings in detail
patchsmith analyze --detailed-limit 10

# Save results to file
patchsmith analyze -o results.json
```

**What it does:**
1. Detects programming languages in your project
2. Creates CodeQL database
3. Runs security-focused queries
4. Parses SARIF results
5. Uses AI to triage/prioritize findings
6. Performs detailed security assessment on top issues
7. Computes statistics

**Output:**
- Progress bars showing each step
- Summary table with findings count by severity
- Top 10 findings table
- Recommendations for next steps

---

### `patchsmith report`

Generate a comprehensive security report.

**Usage:**
```bash
patchsmith report [PATH] [OPTIONS]
```

**Options:**
- `-f, --format [markdown|html|text]` - Report format (default: markdown)
- `-o, --output PATH` - Output file path
- `--no-analysis` - Use existing analysis data (not yet implemented)

**Examples:**
```bash
# Generate markdown report
patchsmith report

# Generate HTML report
patchsmith report --format html

# Custom output location
patchsmith report -o ~/reports/security.md

# Report on specific project
patchsmith report ~/code/my-app
```

**What it includes:**
- Executive summary
- Statistics and metrics
- Detailed findings with triage results
- Security assessments (attack scenarios, exploitability)
- Remediation recommendations

**Output:**
- Report saved to `.patchsmith_reports/<project>_security_report.<format>`
- Preview of first 20 lines in terminal

---

### `patchsmith fix`

Generate and optionally apply security fixes.

**Usage:**
```bash
patchsmith fix [FINDING_ID] [OPTIONS]
```

**Options:**
- `-p, --path PATH` - Project path (default: current directory)
- `--apply / --no-apply` - Auto-apply fix (default: no)
- `--branch / --no-branch` - Create Git branch (default: yes)
- `--commit / --no-commit` - Create Git commit (default: yes)
- `-i, --interactive` - Interactive mode

**Examples:**
```bash
# Interactive mode - select from top findings
patchsmith fix --interactive

# Fix specific finding (shows preview, asks for confirmation)
patchsmith fix py/sql-injection-001

# Generate and auto-apply fix
patchsmith fix py/sql-injection-001 --apply

# Apply without Git operations
patchsmith fix py/sql-injection-001 --apply --no-branch --no-commit
```

**What it does:**
1. Finds the vulnerability in your code
2. Uses AI to generate a secure fix
3. Shows original vs. fixed code
4. (Optional) Applies the fix
5. (Optional) Creates Git branch and commit

**Safety:**
- By default, only shows proposed changes
- Requires `--apply` flag to actually modify files
- Creates Git branch by default (easy to undo)
- Shows AI confidence score (only applies if >= 0.7)

---

### `patchsmith init`

Initialize Patchsmith configuration.

**Usage:**
```bash
patchsmith init [PATH] [OPTIONS]
```

**Options:**
- `-n, --name TEXT` - Project name (default: directory name)

**Examples:**
```bash
# Initialize current directory
patchsmith init

# Initialize specific project
patchsmith init ~/code/my-app

# Set custom project name
patchsmith init --name "My App"
```

**What it creates:**
- `.patchsmith/config.json` - Project configuration
- `.patchsmith/.gitignore` - Ignore temporary files
- `.patchsmith/reports/` - Reports directory

---

## Typical Workflow

### First Time Analysis

```bash
# 1. Navigate to your project
cd ~/code/my-app

# 2. Initialize (optional but recommended)
patchsmith init

# 3. Run analysis
patchsmith analyze

# 4. Generate report
patchsmith report

# 5. Fix high-priority issues
patchsmith fix --interactive
```

### Regular Security Checks

```bash
# Quick scan
patchsmith analyze --no-detailed

# Full scan with report
patchsmith analyze && patchsmith report --format html
```

### CI/CD Integration

```bash
# Run analysis and save results
patchsmith analyze --no-detailed -o security-results.json

# Fail build if critical/high findings exist
# (custom script to parse results.json)
```

## Configuration

Configuration is stored in `.patchsmith/config.json`:

```json
{
  "version": "1.0",
  "project": {
    "name": "my-app",
    "root": "/path/to/project"
  },
  "codeql": {
    "database_path": null,
    "query_paths": [],
    "timeout": 600,
    "threads": 4
  },
  "analysis": {
    "filter_false_positives": true,
    "min_severity": "low",
    "max_results": null,
    "batch_size": 10
  },
  "llm": {
    "model": "claude-sonnet-4",
    "temperature": 0.1,
    "max_tokens": 4096,
    "timeout": 300,
    "max_retries": 3
  }
}
```

You can edit this file to customize:
- CodeQL timeout and threads
- Minimum severity to report
- AI model and parameters
- Analysis batch size

## Environment Variables

- `ANTHROPIC_API_KEY` - **Required** - Your Claude API key
- `PATCHSMITH_CONFIG` - Optional - Path to config file
- `CODEQL_PATH` - Optional - Path to CodeQL CLI (default: searches PATH)

## Tips & Best Practices

### Performance

- **First run is slow** - CodeQL database creation takes time
- **Subsequent runs are faster** - Database is cached
- **Use `--no-detailed`** for quick scans
- **Adjust `--detailed-limit`** based on project size

### Accuracy

- **Review AI-generated fixes** - Always inspect before applying
- **Use `--interactive` mode** - Safer than auto-apply
- **Check confidence scores** - Low confidence (<0.7) needs manual review
- **Test after applying fixes** - Run your test suite

### Git Workflow

- **Fixes create branches** - Easy to review and discard
- **Commit messages are descriptive** - Include finding ID and explanation
- **Use `git log` and `git diff`** - Review changes before merging
- **Undo with `git reset --hard HEAD~1`** - If needed

### Large Projects

- **Start with high-severity only** - Use triage to focus
- **Fix incrementally** - Don't try to fix everything at once
- **Generate reports regularly** - Track progress over time
- **Consider CI/CD integration** - Catch issues early

## Troubleshooting

### "CodeQL not found"
```bash
# Install CodeQL and add to PATH
export PATH="/path/to/codeql:$PATH"
```

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY='your-key'
```

### "Analysis failed"
- Check that CodeQL supports your language
- Ensure project has valid source files
- Check logs in `.patchsmith/logs/`

### "No findings"
- ✅ Great! Your code might be secure
- Or: Project might not have detectable patterns
- Or: CodeQL queries might not cover your patterns

### "Fix generation failed"
- Some vulnerabilities require manual fixes
- Complex code context might confuse AI
- Try with different findings

## Getting Help

```bash
# Show version
patchsmith --version

# Show help for any command
patchsmith <command> --help

# Examples
patchsmith analyze --help
patchsmith fix --help
```

## Next Steps

- **Run your first analysis**: `patchsmith analyze`
- **Explore findings**: Check the generated report
- **Try fixing something**: Use interactive mode
- **Integrate into workflow**: Add to CI/CD or pre-commit hooks

Happy securing! 🔒
