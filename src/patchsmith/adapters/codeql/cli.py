"""CodeQL CLI wrapper for database and query operations."""

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from patchsmith.utils.logging import get_logger

logger = get_logger()


class CodeQLError(Exception):
    """CodeQL operation failed."""

    pass


class CodeQLCLI:
    """Wrapper around CodeQL CLI for database and query operations."""

    def __init__(self, codeql_path: str = "codeql") -> None:
        """
        Initialize CodeQL CLI wrapper.

        Args:
            codeql_path: Path to CodeQL executable (default: "codeql" in PATH)

        Raises:
            CodeQLError: If CodeQL is not installed or version check fails
        """
        self.codeql_path = codeql_path
        self.version_info = self._verify_installation()
        logger.info("codeql_initialized", version=self.version_info.get("version"))

    def _verify_installation(self) -> dict[str, Any]:
        """
        Verify CodeQL is installed and get version information.

        Returns:
            Version information dictionary

        Raises:
            CodeQLError: If CodeQL is not found or version check fails
        """
        try:
            result = self._run(["version", "--format=json"])
            version_info: dict[str, Any] = json.loads(result.stdout)
            return version_info
        except FileNotFoundError as e:
            raise CodeQLError(
                f"CodeQL CLI not found at '{self.codeql_path}'. "
                "Please install CodeQL and ensure it's in your PATH. "
                "See: https://github.com/github/codeql-cli-binaries/releases"
            ) from e
        except json.JSONDecodeError as e:
            raise CodeQLError(f"Failed to parse CodeQL version info: {e}") from e

    def _run(
        self,
        args: list[str],
        cwd: Optional[Path] = None,
        timeout: int = 3600,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """
        Execute CodeQL command with error handling.

        Args:
            args: Command arguments (without 'codeql' prefix)
            cwd: Working directory for command execution
            timeout: Command timeout in seconds (default: 1 hour)
            capture_output: Whether to capture stdout/stderr

        Returns:
            Completed process with stdout/stderr

        Raises:
            CodeQLError: If command fails or times out
        """
        cmd = [self.codeql_path] + args
        cmd_str = " ".join(cmd)

        logger.debug("codeql_command_starting", command=cmd_str, cwd=str(cwd) if cwd else None)

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=True,
            )

            logger.debug(
                "codeql_command_completed",
                command=cmd_str,
                returncode=result.returncode,
                stdout_length=len(result.stdout) if result.stdout else 0,
            )

            return result

        except subprocess.CalledProcessError as e:
            logger.error(
                "codeql_command_failed",
                command=cmd_str,
                returncode=e.returncode,
                stderr=e.stderr[:500] if e.stderr else None,  # Truncate long errors
            )
            raise CodeQLError(
                f"CodeQL command failed (exit code {e.returncode}): {cmd_str}\n"
                f"Error: {e.stderr}"
            ) from e

        except subprocess.TimeoutExpired as e:
            logger.error("codeql_command_timeout", command=cmd_str, timeout=timeout)
            raise CodeQLError(
                f"CodeQL command timed out after {timeout}s: {cmd_str}"
            ) from e

        except FileNotFoundError as e:
            raise CodeQLError(
                f"CodeQL executable not found: {self.codeql_path}"
            ) from e

    def get_version(self) -> str:
        """
        Get CodeQL CLI version string.

        Returns:
            Version string (e.g., "2.15.3")
        """
        version: str = self.version_info.get("version", "unknown")
        return version

    def check_database_exists(self, db_path: Path) -> bool:
        """
        Check if a CodeQL database exists and is valid.

        Args:
            db_path: Path to database directory

        Returns:
            True if database exists and appears valid
        """
        if not db_path.exists():
            return False

        # Check for codeql-database.yml file (present in all CodeQL databases)
        db_yml = db_path / "codeql-database.yml"
        return db_yml.exists()

    def create_database(
        self,
        source_root: Path,
        db_path: Path,
        language: str,
        threads: int = 0,
        overwrite: bool = False,
        build_command: Optional[str] = None,
    ) -> None:
        """
        Create a CodeQL database for a language.

        Args:
            source_root: Root directory of source code to analyze
            db_path: Path where database should be created
            language: Language to analyze (python, javascript, java, go, etc.)
            threads: Number of threads to use (0 = auto)
            overwrite: Whether to overwrite existing database
            build_command: Custom build command (for compiled languages like Java/C++)

        Raises:
            CodeQLError: If database creation fails
        """
        if not source_root.exists():
            raise CodeQLError(f"Source root does not exist: {source_root}")

        if not source_root.is_dir():
            raise CodeQLError(f"Source root is not a directory: {source_root}")

        # Check if database already exists
        if self.check_database_exists(db_path):
            if not overwrite:
                logger.info(
                    "codeql_database_exists",
                    db_path=str(db_path),
                    language=language,
                )
                return
            else:
                logger.warning(
                    "codeql_database_overwriting",
                    db_path=str(db_path),
                    language=language,
                )

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Build command arguments
        args = [
            "database",
            "create",
            str(db_path),
            f"--language={language}",
            f"--source-root={source_root}",
        ]

        if build_command:
            args.append(f"--command={build_command}")

        if threads > 0:
            args.append(f"--threads={threads}")

        if overwrite:
            args.append("--overwrite")

        logger.info(
            "codeql_database_creation_started",
            language=language,
            source_root=str(source_root),
            db_path=str(db_path),
        )

        try:
            # Database creation can take a while, use longer timeout
            self._run(args, timeout=1800)  # 30 minutes

            logger.info(
                "codeql_database_creation_completed",
                language=language,
                db_path=str(db_path),
            )

        except CodeQLError as e:
            logger.error(
                "codeql_database_creation_failed",
                language=language,
                db_path=str(db_path),
                error=str(e),
            )

            # Provide helpful error messages for common issues
            error_msg = str(e).lower()
            if "autobuild" in error_msg and language in ["java", "csharp", "cpp", "go"]:
                hint = (
                    f"\n\nCodeQL autobuild failed for {language}. This usually means:\n"
                    f"  • The project's build system isn't recognized\n"
                    f"  • Build dependencies are missing\n"
                    f"  • The project requires custom build steps\n\n"
                    f"Solutions:\n"
                    f"  1. Ensure build tools are installed (Maven/Gradle for Java)\n"
                    f"  2. Try building the project manually first\n"
                    f"  3. Use a custom build command (future feature)\n"
                )
                raise CodeQLError(str(e) + hint) from e

            raise

    def run_queries(
        self,
        db_path: Path,
        query_path: Path | str,
        output_format: str = "sarif-latest",
        output_path: Optional[Path] = None,
        threads: int = 0,
        download: bool = True,
    ) -> Path:
        """
        Execute CodeQL queries against a database.

        Args:
            db_path: Path to CodeQL database
            query_path: Path to query file (.ql), directory, or query pack name
            output_format: Output format (sarif-latest, csv, json, etc.)
            output_path: Where to write results (auto-generated if None)
            threads: Number of threads to use (0 = auto)
            download: Download missing query packs automatically

        Returns:
            Path to results file

        Raises:
            CodeQLError: If query execution fails
        """
        if not self.check_database_exists(db_path):
            raise CodeQLError(f"Database does not exist: {db_path}")

        # Allow query pack names (strings) or file paths
        query_path_obj = Path(query_path) if isinstance(query_path, str) else query_path

        # Only check existence if it's a file path (not a pack name)
        if isinstance(query_path, Path) and not query_path.exists():
            raise CodeQLError(f"Query path does not exist: {query_path}")

        # Auto-generate output path if not provided
        if output_path is None:
            extension = self._get_extension_for_format(output_format)
            output_path = db_path.parent / f"results.{extension}"

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build command arguments
        args = [
            "database",
            "analyze",
            str(db_path),
            str(query_path),
            f"--format={output_format}",
            f"--output={output_path}",
            "--rerun",  # Always rerun queries (don't use cached results)
        ]

        if download:
            args.append("--download")  # Download missing query packs

        if threads > 0:
            args.append(f"--threads={threads}")

        logger.info(
            "codeql_query_execution_started",
            database=str(db_path),
            queries=str(query_path),
            output_format=output_format,
        )

        try:
            # Query execution can take a while, use longer timeout
            self._run(args, timeout=3600)  # 1 hour

            logger.info(
                "codeql_query_execution_completed",
                database=str(db_path),
                output=str(output_path),
            )

            return output_path

        except CodeQLError as e:
            logger.error(
                "codeql_query_execution_failed",
                database=str(db_path),
                queries=str(query_path),
                error=str(e),
            )
            raise

    def _get_extension_for_format(self, format: str) -> str:
        """
        Get file extension for output format.

        Args:
            format: Output format name

        Returns:
            File extension (without dot)
        """
        format_extensions = {
            "sarif-latest": "sarif",
            "sarifv2.1.0": "sarif",
            "csv": "csv",
            "json": "json",
            "text": "txt",
        }
        return format_extensions.get(format, format)

    def delete_database(self, db_path: Path) -> None:
        """
        Delete a CodeQL database.

        Args:
            db_path: Path to database to delete

        Raises:
            CodeQLError: If deletion fails
        """
        if not db_path.exists():
            logger.warning("codeql_database_not_exists", database=str(db_path))
            return

        logger.info("codeql_database_deletion_started", database=str(db_path))

        try:
            import shutil

            shutil.rmtree(db_path)

            logger.info("codeql_database_deleted", database=str(db_path))

        except Exception as e:
            raise CodeQLError(f"Failed to delete database: {e}") from e

    def get_database_info(self, db_path: Path) -> dict[str, str]:
        """
        Get information about a CodeQL database.

        Args:
            db_path: Path to database

        Returns:
            Dictionary with database metadata

        Raises:
            CodeQLError: If database doesn't exist or info retrieval fails
        """
        if not self.check_database_exists(db_path):
            raise CodeQLError(f"Database does not exist: {db_path}")

        # Read codeql-database.yml for metadata
        db_yml = db_path / "codeql-database.yml"
        if not db_yml.exists():
            raise CodeQLError(f"Database metadata file missing: {db_yml}")

        try:
            import yaml

            with open(db_yml) as f:
                metadata = yaml.safe_load(f)

            if metadata is None or not isinstance(metadata, dict):
                raise CodeQLError(f"Database metadata file missing: {db_yml}")

            # Extract creation time and convert to string if datetime
            created = metadata.get("creationMetadata", {}).get(
                "creationTime", "unknown"
            )
            if hasattr(created, "isoformat"):
                created = created.isoformat()

            return {
                "name": metadata.get("name", "unknown"),
                "language": metadata.get("primaryLanguage", "unknown"),
                "created": str(created),
            }

        except CodeQLError:
            raise
        except Exception as e:
            raise CodeQLError(f"Failed to read database info: {e}") from e

    def upgrade_database(self, db_path: Path) -> None:
        """
        Upgrade a CodeQL database to the current CLI version.

        Args:
            db_path: Path to database

        Raises:
            CodeQLError: If upgrade fails
        """
        if not self.check_database_exists(db_path):
            raise CodeQLError(f"Database does not exist: {db_path}")

        logger.info("codeql_database_upgrade_started", database=str(db_path))

        args = ["database", "upgrade", str(db_path)]

        try:
            self._run(args)

            logger.info("codeql_database_upgraded", database=str(db_path))

        except CodeQLError as e:
            logger.error(
                "codeql_database_upgrade_failed",
                database=str(db_path),
                error=str(e),
            )
            raise

    def create_ql_pack(
        self,
        pack_dir: Path,
        language: str,
        pack_name: str = "patchsmith-custom-queries",
    ) -> None:
        """
        Create a CodeQL pack structure with qlpack.yml.

        Args:
            pack_dir: Directory to create pack in
            language: Target language (python, javascript, java, etc.)
            pack_name: Name of the pack (default: patchsmith-custom-queries)

        Raises:
            CodeQLError: If pack creation fails
        """
        pack_dir.mkdir(parents=True, exist_ok=True)

        # Create qlpack.yml
        qlpack_path = pack_dir / "qlpack.yml"

        # Map language to standard library pack
        # Note: TypeScript uses the same pack as JavaScript in CodeQL
        standard_libs = {
            "python": "codeql/python-all",
            "javascript": "codeql/javascript-all",
            "typescript": "codeql/javascript-all",  # TypeScript uses JS pack
            "java": "codeql/java-all",
            "go": "codeql/go-all",
            "cpp": "codeql/cpp-all",
            "c": "codeql/cpp-all",  # C uses the same pack as C++
            "csharp": "codeql/csharp-all",
            "ruby": "codeql/ruby-all",
        }

        standard_lib = standard_libs.get(language.lower())
        if not standard_lib:
            raise CodeQLError(f"Unsupported language for QL pack: {language}")

        # Create qlpack.yml content
        qlpack_content = f"""name: patchsmith/{pack_name}-{language}
version: 0.0.1
dependencies:
  {standard_lib}: "*"
"""

        qlpack_path.write_text(qlpack_content)

        logger.info(
            "ql_pack_created",
            pack_dir=str(pack_dir),
            language=language,
        )

    def install_pack_dependencies(self, pack_dir: Path) -> None:
        """
        Install dependencies for a CodeQL pack.

        This runs `codeql pack install` to download dependencies
        declared in qlpack.yml.

        Args:
            pack_dir: Directory containing qlpack.yml

        Raises:
            CodeQLError: If pack installation fails
        """
        qlpack_path = pack_dir / "qlpack.yml"
        if not qlpack_path.exists():
            raise CodeQLError(
                f"qlpack.yml not found in {pack_dir}. "
                "Create pack structure first with create_ql_pack()"
            )

        logger.info("pack_install_started", pack_dir=str(pack_dir))

        args = ["pack", "install", str(pack_dir)]

        try:
            # Pack installation can take a while
            self._run(args, cwd=pack_dir, timeout=300)

            logger.info("pack_install_completed", pack_dir=str(pack_dir))

        except CodeQLError as e:
            logger.error(
                "pack_install_failed",
                pack_dir=str(pack_dir),
                error=str(e),
            )
            raise

    def compile_query(
        self,
        query_path: Path,
        check_only: bool = True,
    ) -> tuple[bool, str]:
        """
        Compile or validate a CodeQL query.

        This method can be used to:
        1. Validate query syntax (check_only=True) - fast validation
        2. Fully compile a query (check_only=False) - slower, generates query plan

        Args:
            query_path: Path to .ql query file
            check_only: If True, only validate syntax without full compilation

        Returns:
            Tuple of (success: bool, error_message: str)
            - If successful: (True, "")
            - If failed: (False, error_message)

        Raises:
            CodeQLError: If query file doesn't exist or is not a .ql file
        """
        if not query_path.exists():
            raise CodeQLError(f"Query file does not exist: {query_path}")

        if query_path.suffix != ".ql":
            raise CodeQLError(
                f"Query file must have .ql extension: {query_path}"
            )

        # Build command arguments
        args = ["query", "compile"]

        if check_only:
            args.append("--check-only")

        args.append(str(query_path))

        logger.info(
            "codeql_query_compilation_started",
            query=str(query_path),
            check_only=check_only,
        )

        try:
            # Run compilation (shorter timeout for check-only)
            timeout = 60 if check_only else 300
            result = self._run(args, timeout=timeout)

            logger.info(
                "codeql_query_compilation_completed",
                query=str(query_path),
            )

            return (True, "")

        except CodeQLError as e:
            # Extract error message from stderr
            error_msg = str(e)

            logger.warning(
                "codeql_query_compilation_failed",
                query=str(query_path),
                error=error_msg[:500],  # Truncate long errors
            )

            # Return failure with error message (don't raise)
            return (False, error_msg)
