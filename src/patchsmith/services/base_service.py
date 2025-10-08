"""Base service class for business logic layer."""

from typing import Any, Callable

from patchsmith.models.config import PatchsmithConfig
from patchsmith.utils.logging import get_logger

logger = get_logger()


class BaseService:
    """Base class for all services.

    Services contain business logic and orchestrate adapters. They are
    presentation-agnostic and communicate via progress callbacks rather
    than direct output.
    """

    def __init__(
        self,
        config: PatchsmithConfig,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Initialize base service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional callback for progress updates
                               Signature: (event_name: str, data: dict)
        """
        self.config = config
        self.progress_callback = progress_callback
        self.service_name = self.__class__.__name__

        logger.debug(
            "service_initialized",
            service=self.service_name,
            has_progress_callback=progress_callback is not None,
        )

    def _emit_progress(self, event: str, **kwargs: Any) -> None:
        """
        Emit a progress event.

        Args:
            event: Event name (e.g., "analysis_started", "step_completed")
            **kwargs: Additional event data
        """
        if self.progress_callback:
            data = {"service": self.service_name, **kwargs}
            try:
                self.progress_callback(event, data)
            except Exception as e:
                # Don't let callback errors break the service
                logger.warning(
                    "progress_callback_error",
                    service=self.service_name,
                    event_name=event,
                    error=str(e),
                )

        # Also log progress events
        logger.debug(
            "progress_event",
            service=self.service_name,
            event_name=event,
            data=kwargs,
        )
