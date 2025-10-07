# Patchsmith

**Your AI-Powered Security Apprentice: From Vulnerability Detection to Pull Request in Minutes**

Patchsmith is an intelligent CLI tool that automates the entire security vulnerability lifecycle using CodeQL's powerful analysis engine enhanced with Claude's code understanding.

## Features

- 🔍 **Intelligent Analysis**: Detects security vulnerabilities using CodeQL
- 🤖 **AI-Powered**: Uses Claude to filter false positives and generate fixes
- 🔧 **Automated Fixes**: Generates pull requests with security patches
- 📊 **Clear Reports**: Human-readable security analysis reports
- ⚡ **CLI-First**: Fast, terminal-based workflow

## Quick Start

```bash
# Install
pip install patchsmith

# Initialize in your project
patchsmith init

# Run security analysis
patchsmith analyze

# Fix a vulnerability
patchsmith fix ISSUE-001

# View report
patchsmith report
```

## Prerequisites

- Python 3.9+
- CodeQL CLI (installed and in PATH)
- Git
- Claude API key (set `ANTHROPIC_API_KEY` environment variable)

## Documentation

- [User Guide](documentation/user-guide.md)
- [Requirements](documentation/requirements.md)
- [Technical Design](documentation/design.md)
- [Product Pitch](documentation/product.md)

## Development Status

🚧 **Alpha** - Under active development

## License

TBD

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.
