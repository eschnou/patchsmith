"""Audit logging system with rotation."""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

import structlog


class AuditLogger:
    """Audit logger with file rotation for security-sensitive operations."""

    def __init__(
        self,
        log_file: Path,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> None:
        """
        Initialize audit logger with rotation.

        Args:
            log_file: Path to audit log file
            max_bytes: Maximum size of log file before rotation (default: 10MB)
            backup_count: Number of rotated log files to keep (default: 5)
        """
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._setup()

    def _setup(self) -> None:
        """Setup the audit logger with rotation."""
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            str(self.log_file),
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
        )
        handler.setLevel(logging.INFO)

        # JSON formatter for structured audit logs
        json_processor = structlog.processors.JSONRenderer()

        class StructlogFormatter(logging.Formatter):
            """Formatter that uses structlog JSON renderer."""

            def format(self, record: logging.LogRecord) -> str:
                # Convert LogRecord to dict
                event_dict = {
                    "event": record.getMessage(),
                    "level": record.levelname.lower(),
                    "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
                    "logger": record.name,
                }
                # Add extra fields
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                    ]:
                        event_dict[key] = value

                result = json_processor(None, None, event_dict)  # type: ignore[arg-type]
                return result if isinstance(result, str) else result.decode("utf-8")

        handler.setFormatter(StructlogFormatter())

        # Create and configure audit logger
        self.logger = logging.getLogger("patchsmith.audit")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.propagate = False  # Don't propagate to root logger

    def log(self, event: str, **kwargs: object) -> None:
        """
        Log an audit event.

        Args:
            event: Event name/description
            **kwargs: Additional event data
        """
        self.logger.info(event, extra=kwargs)

    def log_command(
        self, command: str, command_args: Optional[dict[str, object]] = None, **kwargs: object
    ) -> None:
        """
        Log a CLI command execution.

        Args:
            command: Command name (e.g., 'init', 'analyze')
            command_args: Command arguments
            **kwargs: Additional context
        """
        self.log("command_executed", command=command, command_args=command_args, **kwargs)

    def log_operation(self, operation: str, status: str, **kwargs: object) -> None:
        """
        Log an operation with status.

        Args:
            operation: Operation name
            status: Operation status (success, failed, started)
            **kwargs: Additional context
        """
        self.log("operation", operation=operation, status=status, **kwargs)

    def log_security_event(self, event_type: str, severity: str, **kwargs: object) -> None:
        """
        Log a security-related event.

        Args:
            event_type: Type of security event
            severity: Severity level
            **kwargs: Additional context
        """
        self.log("security_event", event_type=event_type, severity=severity, **kwargs)


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(
    log_file: Optional[Path] = None,
) -> AuditLogger:
    """
    Get or create the global audit logger instance.

    Args:
        log_file: Optional path to audit log file.
                  Defaults to .patchsmith/audit.log in current directory.

    Returns:
        AuditLogger instance
    """
    global _audit_logger

    if _audit_logger is None:
        if log_file is None:
            log_file = Path.cwd() / ".patchsmith" / "audit.log"
        _audit_logger = AuditLogger(log_file)

    return _audit_logger
