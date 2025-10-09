# Patchsmith CLI Guide

Welcome to Patchsmith! This guide will help you get started with the CLI.

## Prerequisites

1. **Install Patchsmith**:
   ```bash
   poetry install
   ```

2. **Set up API Key** (required for AI features):

   **Option A: During initialization (recommended):**
   ```bash
   patchsmith init --save-api-key
   ```
   This will prompt for your key and save it to `~/.patchsmith/config.yaml`

   **Option B: Environment variable:**
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

   Or add to your shell profile:
   ```bash
   echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.zshrc  # or ~/.bashrc
   source ~/.zshrc
   ```

   **Option C: Manual user config file:**

   Create `~/.patchsmith/config.yaml`:
   ```yaml
   anthropic_api_key: 'your-api-key-here'
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
- `--investigate` - Run deep AI investigation on top 10 priority groups (default: off)
- `--investigate-all` - Run deep AI investigation on ALL findings (slow, expensive)
- `--custom-only` - Only run custom CodeQL queries (skip built-in queries)
- `-o, --output PATH` - Save results to JSON file

**Examples:**
```bash
# Quick analysis (triage only, no investigation)
patchsmith analyze

# Full analysis with deep investigation of top 10 groups
patchsmith analyze --investigate

# Analyze specific project
patchsmith analyze ~/code/my-app --investigate

# Investigate ALL findings (warning: slow and expensive!)
patchsmith analyze --investigate-all

# Save results to file
patchsmith analyze -o results.json
```

**What it does:**
1. Detects programming languages in your project
2. Creates CodeQL database (or reuses cached one)
3. Runs security-focused CodeQL queries
4. Parses SARIF results into findings
5. **Always triages ALL findings** - groups similar patterns, assigns priority scores
6. (Optional) Performs deep AI investigation on top priority groups

**Analysis Modes:**

- **Default (triage only)**: Fast analysis that groups findings and assigns priority scores. Top 10 groups marked for investigation but not actually investigated yet. Use this for quick scans.

- **With `--investigate`**: Full analysis that investigates the top 10 priority groups with AI. Each group gets detailed security assessment (attack scenarios, exploitability, impact). Recommended for thorough security reviews.

- **With `--investigate-all`**: Investigates EVERY finding/group with AI. Very slow and expensive - only use when you need complete coverage.

**Finding Grouping:**

Patchsmith automatically groups similar findings to avoid redundant investigations:
- Same vulnerability type + same file + similar pattern = ONE group
- Groups shown with 🔗×N indicator (e.g., `F-20 🔗×6` = 6 instances)
- AI investigates the representative finding, applies insights to all instances
- Saves time and API costs while maintaining thorough analysis

**Output:**
- Progress bars showing each step
- Triage table with top 10 prioritized groups (shows grouping indicators)
- Summary statistics by severity
- Results cached in `.patchsmith/results.json` for later use

---

### `patchsmith report`

Generate a comprehensive security report from cached analysis results.

**Usage:**
```bash
patchsmith report [PATH] [OPTIONS]
```

**Options:**
- `-f, --format [markdown|html]` - Report format (default: markdown)
- `-o, --output PATH` - Output file path

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
- Executive summary with key risks and immediate actions
- Statistics and metrics (counts by severity, most common CWEs)
- **Prioritized findings** organized by remediation priority (Immediate/High/Medium/Low)
- **Additional findings** - triaged but not deeply investigated (summary table)
- Detailed security assessments for investigated findings (attack scenarios, exploitability)
- Remediation recommendations

**Report Sections:**

1. **Immediate/High/Medium/Low Priority Findings**: Deeply investigated findings with AI analysis, organized by remediation urgency. Shows grouping info (🔗×N) and related instances.

2. **Additional Findings (Triaged, Not Deeply Analyzed)**: Summary table of findings that were triaged and prioritized but not selected for deep investigation. Includes priority scores and grouping information.

**Output:**
- Report saved to `.patchsmith/reports/<project>_security_report.<format>`
- Preview of first 20 lines in terminal

**Note:** Report reads from cached results in `.patchsmith/results.json`. Run `patchsmith analyze` first to generate/update the data.

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

### `patchsmith finetune`

Generate custom CodeQL queries tailored to your project's patterns and architecture.

**Usage:**
```bash
patchsmith finetune [PATH] [OPTIONS]
```

**Options:**
- `-o, --output PATH` - Output directory for custom queries (default: `.patchsmith/custom_queries/`)

**Examples:**
```bash
# Generate custom queries for current project
patchsmith finetune

# Generate for specific project
patchsmith finetune ~/code/my-app

# Save to custom location
patchsmith finetune -o ~/queries/
```

**What it does:**
1. Analyzes your project's code patterns and architecture
2. Identifies language-specific security risks
3. Uses AI to generate targeted CodeQL queries
4. Saves queries to `.patchsmith/custom_queries/`

**Custom queries are automatically used in future analysis runs.**

**Output:**
- Custom query files (`.ql` files)
- Query suite file referencing all custom queries
- Summary of generated queries

---

### `patchsmith investigate`

Run deep AI security investigation on a specific finding or group.

**Usage:**
```bash
patchsmith investigate <FINDING_ID> [PATH] [OPTIONS]
```

**Arguments:**
- `FINDING_ID` - The finding ID to investigate (e.g., `F-20`)

**Examples:**
```bash
# Investigate specific finding
patchsmith investigate F-20

# Investigate finding in specific project
patchsmith investigate F-20 ~/code/my-app
```

**What it does:**
1. Loads the finding from cached results
2. Runs detailed AI security assessment
3. Analyzes attack scenarios and exploitability
4. Provides impact analysis and remediation guidance
5. Updates cached results with investigation data

**Use this when:**
- You want to investigate a specific finding that wasn't in the top 10
- You need more detail on a particular vulnerability
- You're reviewing triaged findings from the "Additional Findings" section

**Output:**
- Detailed analysis printed to console
- Results saved to `.patchsmith/results.json`

---

### `patchsmith list`

List all findings from the last analysis with grouping and triage information.

**Usage:**
```bash
patchsmith list [PATH] [OPTIONS]
```

**Options:**
- `--severity [critical|high|medium|low|info]` - Filter by severity
- `--limit INTEGER` - Max findings to show (default: 50)
- `--show-all` - Show all findings (no limit)

**Examples:**
```bash
# List top 50 findings
patchsmith list

# Show only critical findings
patchsmith list --severity critical

# Show all findings
patchsmith list --show-all

# List findings for specific project
patchsmith list ~/code/my-app
```

**What it shows:**
- Finding ID with grouping indicator (🔗×N if grouped)
- Priority score (from triage)
- Severity level
- Vulnerability type (rule ID)
- Location (file:line)

**Output:**
- Formatted table with all findings
- Groups are shown with their total instance count
- Color-coded by severity

---

### `patchsmith clean`

Clean cached analysis data and temporary files.

**Usage:**
```bash
patchsmith clean [PATH] [OPTIONS]
```

**Options:**
- `--all` - Remove CodeQL database and all cached data
- `--reports` - Remove generated reports only
- `--db` - Remove CodeQL database only

**Examples:**
```bash
# Clean cached results (keeps database for faster re-analysis)
patchsmith clean

# Remove everything including database
patchsmith clean --all

# Remove only reports
patchsmith clean --reports
```

**What it cleans:**
- `.patchsmith/results.json` - Cached analysis results
- `.patchsmith/reports/` - Generated reports
- `.patchsmith/codeql_db/` - CodeQL database (with `--hard`)

**Note:** Cleaning the database will require full CodeQL analysis on next run (slower).

---

## Typical Workflow

### First Time Analysis

```bash
# 1. Navigate to your project
cd ~/code/my-app

# 2. Initialize (optional but recommended)
patchsmith init

# 3. Run full analysis with investigation
patchsmith analyze --investigate

# 4. Generate HTML report
patchsmith report --format html

# 5. Fix high-priority issues
patchsmith fix --interactive
```

### Quick Security Check (Triage Only)

```bash
# Run quick triage (no investigation)
patchsmith analyze

# View findings
patchsmith list

# Investigate specific concerning finding
patchsmith investigate F-20
```

### Advanced Workflow with Custom Queries

```bash
# 1. Generate project-specific queries
patchsmith finetune

# 2. Run analysis with custom queries
patchsmith analyze --investigate

# 3. Generate comprehensive report
patchsmith report --format html
```

### Regular Security Checks

```bash
# Quick scan (triage only, no investigation)
patchsmith analyze

# Full scan with deep investigation and report
patchsmith analyze --investigate && patchsmith report --format html

# Investigate only custom query findings
patchsmith analyze --custom-only --investigate
```

### CI/CD Integration

```bash
# Run quick analysis and save results
patchsmith analyze -o security-results.json

# Generate report for artifacts
patchsmith report --format html

# Fail build if critical/high findings exist
# (custom script to parse security-results.json)
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

## Configuration

### API Key Setup

Patchsmith needs an Anthropic API key. Configure it using:

**1. User config file (recommended):**
- Location: `~/.patchsmith/config.yaml`
- Run: `patchsmith init --save-api-key`
- Permissions: Automatically set to 600 (owner only)

**2. Environment variable:**
- `ANTHROPIC_API_KEY` - Your Claude API key
- Good for CI/CD or temporary overrides

**Priority:** Environment variable takes precedence over user config file.

### Other Environment Variables

- `PATCHSMITH_CONFIG` - Optional - Path to project config file
- `CODEQL_PATH` - Optional - Path to CodeQL CLI (default: searches PATH)
- `PATCHSMITH_MODEL` - Optional - Override LLM model
- `PATCHSMITH_MIN_SEVERITY` - Optional - Override minimum severity

## Tips & Best Practices

### Performance

- **First run is slow** - CodeQL database creation takes time (5-20 minutes for large projects)
- **Subsequent runs are faster** - Database is cached in `.patchsmith/codeql_db/`
- **Use default mode** for quick scans (triage only, no investigation)
- **Use `--investigate`** only when you need deep analysis (adds 10-30 minutes)
- **Avoid `--investigate-all`** unless absolutely necessary (very slow and expensive)

### Analysis Strategy

- **Start with triage**: Run `patchsmith analyze` to get prioritized findings
- **Review top 10 groups**: Check if the grouping makes sense
- **Investigate selectively**: Use `patchsmith investigate F-X` for specific findings
- **Use `--investigate`** for comprehensive reports (top 10 groups get deep analysis)
- **Understanding grouping**: 🔗×N indicator shows N instances of same pattern, AI analyzes representative

### Accuracy

- **Review AI-generated fixes** - Always inspect before applying
- **Use `--interactive` mode** - Safer than auto-apply
- **Check confidence scores** - Low confidence (<0.7) needs manual review
- **Test after applying fixes** - Run your test suite
- **Verify grouped findings** - Representative analysis applies to all instances, but check edge cases

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
