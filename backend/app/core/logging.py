import sys

from loguru import logger

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
        ),
    )


__all__ = ["configure_logging", "logger"]
