from __future__ import annotations

import sys
from pathlib import Path
from loguru import logger


def configure_logging(data_dir: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    if data_dir is not None:
        log_dir = data_dir / "outputs" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_dir / "asr_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=lambda record: "asr_service" in record["name"],
        )


def get_logger():
    return logger
