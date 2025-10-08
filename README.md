# 🔒 Patchsmith

**AI-Powered Security Vulnerability Detection and Fixing**

Patchsmith combines the power of [CodeQL](https://codeql.github.com/) static analysis with [Claude AI](https://www.anthropic.com/claude) to automatically detect, triage, and fix security vulnerabilities in your codebase.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## ✨ Features

- 🔍 **Static Analysis** - Powered by GitHub's CodeQL engine
- 🤖 **AI Triage** - Intelligent prioritization of security findings
- 🔬 **Detailed Assessment** - Comprehensive security analysis with attack scenarios
- 🛠️ **Automated Fixing** - AI-generated patches for vulnerabilities
- 📊 **Rich Reports** - Detailed reports in Markdown, HTML, or text
- 🎨 **Beautiful CLI** - Intuitive interface with progress tracking
- 🔄 **Git Integration** - Automatic branching and commits for fixes

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
   ```bash
   python --version  # Should be 3.10 or higher
   ```

2. **CodeQL CLI** (required for analysis)
   ```bash
   # Download from GitHub releases
   # https://github.com/github/codeql-cli-binaries/releases

   # On macOS with Homebrew:
   brew install codeql

   # Verify installation:
   codeql version
   ```

3. **Anthropic API Key** (required for AI features)
   - Sign up at [console.anthropic.com](https://console.anthropic.com/)
   - Get your API key
   - Configure using one of these methods:
     ```bash
     # Option 1: Save to user config (recommended)
     patchsmith init --save-api-key

     # Option 2: Environment variable
     export ANTHROPIC_API_KEY='your-api-key-here'

     # Option 3: Create ~/.patchsmith/config.yaml
     # anthropic_api_key: 'your-api-key-here'
     ```

### Installation

#### Option 1: Install from Source (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/patchsmith.git
cd patchsmith

# Install with Poetry
poetry install

# Run Patchsmith
poetry run patchsmith --help
```

#### Option 2: Install with pip (Coming Soon)

```bash
pip install patchsmith
```

## 📖 Usage

### Initialize a Project

```bash
cd /path/to/your/project
patchsmith init
```

### Run Security Analysis

```bash
# Analyze current directory
patchsmith analyze

# Analyze specific project
patchsmith analyze /path/to/project

# Save results to file
patchsmith analyze -o results.json
```

### Generate Report

```bash
# Generate markdown report
patchsmith report

# Generate HTML report
patchsmith report --format html
```

### Fix Vulnerabilities

```bash
# Interactive mode (recommended)
patchsmith fix --interactive

# Fix specific finding
patchsmith fix <finding-id>

# Auto-apply fix (use with caution!)
patchsmith fix <finding-id> --apply
```

## 📚 Documentation

- **[CLI Guide](CLI_GUIDE.md)** - Complete command reference and examples
- **[Architecture](documentation/design.md)** - Technical design and architecture
- **[Requirements](documentation/requirements.md)** - Full requirements specification

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         CLI Layer (Rich UI)              │
├─────────────────────────────────────────┤
│  Service Layer (Business Logic)          │
│  • AnalysisService                       │
│  • ReportService                         │
│  • FixService                            │
├─────────────────────────────────────────┤
│  Adapter Layer (External Integrations)   │
│  • CodeQL CLI                            │
│  • Claude AI                             │
│  • Git                                   │
└─────────────────────────────────────────┘
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov

# Run manual end-to-end test
poetry run python tests/manual_test_service_layer.py /path/to/project
```

## 📋 Development Status

🚧 **Alpha** - Core features implemented and working. Under active development.

**Current Status:**
- ✅ Phase 1: Foundation (Infrastructure, Models)
- ✅ Phase 2: Adapters (CodeQL, Claude AI, Git)
- ✅ Phase 3: Service Layer
- ✅ Phase 4: CLI Layer
- 🔄 Phase 5: Data Layer (Planned)

## 📜 License

MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[CodeQL](https://codeql.github.com/)** - Semantic code analysis by GitHub
- **[Claude AI](https://www.anthropic.com/claude)** - AI assistant by Anthropic
- **[Rich](https://rich.readthedocs.io/)** - Beautiful terminal formatting

---

**Made with ❤️ for secure software development**
