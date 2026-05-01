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
        # 专用 ASR 日志（debug 级，只收 asr_service 模块）
        logger.add(
            str(log_dir / "asr_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=lambda record: "asr_service" in record["name"],
        )
        # 系统级应用日志（info+，收 ASR 之外所有模块）—— 给"日志查看器"系统 tab 用
        logger.add(
            str(log_dir / "app_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="INFO",
            filter=lambda record: "asr_service" not in record["name"],
        )


def get_logger():
    return logger
