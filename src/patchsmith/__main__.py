"""Allow running patchsmith as a module: python -m patchsmith"""

from patchsmith.cli.main import cli

if __name__ == "__main__":
    cli()
