import logging
from typing import Any, Dict

from rich.logging import RichHandler


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


def event(msg: str, extra: Dict[str, Any] | None = None, level: int = logging.INFO) -> None:
    logging.log(level, msg, extra=extra or {})
