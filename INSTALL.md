# Installation Guide

## Method 1: Install from Source (Recommended for Development)

### Prerequisites
- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) (Python dependency manager)
- Git

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/patchsmith.git
   cd patchsmith
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Verify installation:**
   ```bash
   poetry run patchsmith --version
   ```

4. **Run Patchsmith:**
   ```bash
   poetry run patchsmith --help
   ```

### Optional: Install in virtual environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with Poetry
poetry install

# Patchsmith is now available as a command
patchsmith --help
```

## Method 2: Install from Built Package

### Build the package

```bash
# From the project root
poetry build
```

This creates two files in `dist/`:
- `patchsmith-0.1.0.tar.gz` (source distribution)
- `patchsmith-0.1.0-py3-none-any.whl` (wheel)

### Install the wheel

```bash
pip install dist/patchsmith-0.1.0-py3-none-any.whl
```

Or install from the source distribution:

```bash
pip install dist/patchsmith-0.1.0.tar.gz
```

### Verify installation

```bash
patchsmith --version
```

## Method 3: Install from PyPI (Coming Soon)

Once published to PyPI, you'll be able to install with:

```bash
pip install patchsmith
```

## External Dependencies

Patchsmith requires these external tools:

### 1. CodeQL CLI

CodeQL is required for static analysis.

**macOS (Homebrew):**
```bash
brew install codeql
```

**Linux/macOS (Manual):**
```bash
# Download from GitHub releases
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip
export PATH="$PWD/codeql:$PATH"

# Add to your shell profile for persistence
echo 'export PATH="/path/to/codeql:$PATH"' >> ~/.bashrc
```

**Verify installation:**
```bash
codeql version
```

### 2. Anthropic API Key

Required for AI-powered features (triage, detailed analysis, fix generation).

1. Sign up at https://console.anthropic.com/
2. Generate an API key
3. Set environment variable:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

**Make it permanent** by adding to your shell profile:

```bash
# For bash
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc

# For zsh
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.zshrc
source ~/.zshrc
```

### 3. Git (Optional but Recommended)

Git is required for fix application features (branching, commits).

**Install:**
- macOS: `brew install git` or comes pre-installed
- Linux: `apt-get install git` or `yum install git`
- Windows: Download from https://git-scm.com/

## Troubleshooting

### "Command not found: patchsmith"

If you installed with Poetry:
```bash
# Use poetry run
poetry run patchsmith --help

# OR activate the virtual environment
poetry shell
patchsmith --help
```

If you installed with pip:
```bash
# Check if it's in your PATH
which patchsmith

# If not found, your Python scripts directory may not be in PATH
# Add it to PATH (adjust path as needed):
export PATH="$HOME/.local/bin:$PATH"
```

### "CodeQL not found"

Make sure CodeQL is installed and in your PATH:
```bash
# Check installation
which codeql
codeql version

# If not found, add to PATH
export PATH="/path/to/codeql:$PATH"
```

### "ANTHROPIC_API_KEY not set"

```bash
# Set the environment variable
export ANTHROPIC_API_KEY='your-key'

# Verify it's set
echo $ANTHROPIC_API_KEY
```

### "ImportError" or "ModuleNotFoundError"

If you get import errors:

```bash
# Reinstall dependencies
poetry install --no-cache

# OR with pip
pip install --force-reinstall -e .
```

### Permission errors on macOS/Linux

```bash
# Install for current user only
pip install --user dist/patchsmith-0.1.0-py3-none-any.whl
```

## Development Installation

For development with editable installation:

```bash
# Clone and install in editable mode
git clone https://github.com/yourusername/patchsmith.git
cd patchsmith
poetry install

# Now code changes take effect immediately
poetry run patchsmith --help
```

## Uninstallation

### If installed with pip:
```bash
pip uninstall patchsmith
```

### If installed with Poetry:
```bash
# Remove virtual environment
poetry env remove python
```

## Next Steps

After installation:

1. **Verify everything works:**
   ```bash
   patchsmith --version
   patchsmith --help
   codeql version
   echo $ANTHROPIC_API_KEY
   ```

2. **Initialize a project:**
   ```bash
   cd /path/to/your/project
   patchsmith init
   ```

3. **Run your first analysis:**
   ```bash
   patchsmith analyze
   ```

4. **Read the documentation:**
   - [CLI Guide](CLI_GUIDE.md)
   - [README](README.md)

## Getting Help

If you encounter issues:

1. Check this troubleshooting section
2. Review the [CLI Guide](CLI_GUIDE.md)
3. Search [GitHub Issues](https://github.com/yourusername/patchsmith/issues)
4. Open a new issue with:
   - Your OS and Python version
   - Complete error message
   - Steps to reproduce
