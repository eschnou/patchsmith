"""Repository for project information persistence."""

import json
from pathlib import Path

from patchsmith.models.project import ProjectInfo
from patchsmith.utils.logging import get_logger

logger = get_logger()


class ProjectRepository:
    """Repository for saving/loading project information."""

    @staticmethod
    def get_project_info_path(project_root: Path) -> Path:
        """
        Get the path to project info file.

        Args:
            project_root: Project root directory

        Returns:
            Path to project-info.json
        """
        return project_root / ".patchsmith" / "project-info.json"

    @staticmethod
    def save(project_info: ProjectInfo) -> None:
        """
        Save project information to file.

        Args:
            project_info: Project information to save
        """
        info_path = ProjectRepository.get_project_info_path(project_info.root)
        info_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON-serializable dict
        data = project_info.model_dump(mode="json")

        # Write to file
        info_path.write_text(json.dumps(data, indent=2))

        logger.info(
            "project_info_saved",
            path=str(info_path),
            languages=project_info.get_language_names(),
        )

    @staticmethod
    def load(project_root: Path) -> ProjectInfo | None:
        """
        Load project information from file.

        Args:
            project_root: Project root directory

        Returns:
            ProjectInfo if file exists and is valid, None otherwise
        """
        info_path = ProjectRepository.get_project_info_path(project_root)

        if not info_path.exists():
            logger.debug(
                "project_info_not_found",
                path=str(info_path),
            )
            return None

        try:
            data = json.loads(info_path.read_text())
            project_info = ProjectInfo.model_validate(data)

            logger.info(
                "project_info_loaded",
                path=str(info_path),
                languages=project_info.get_language_names(),
            )

            return project_info

        except Exception as e:
            logger.warning(
                "project_info_load_failed",
                path=str(info_path),
                error=str(e),
            )
            return None

    @staticmethod
    def exists(project_root: Path) -> bool:
        """
        Check if project info file exists.

        Args:
            project_root: Project root directory

        Returns:
            True if project info file exists
        """
        return ProjectRepository.get_project_info_path(project_root).exists()
