from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger


# 让"日志查看器"按模块归档使用的关键字 — 与 log_viewer_service 的类别 glob 对齐。
_ASR_KEY = "asr_service"
_TTS_KEYS = ("tts_service", "app.api.tts")
_COPY_GEN_KEY = "copy_gen"
_VIDEO_GEN_KEYS = ("video_service", "video_gen_service", "app.api.video_gen")


def _record_in(name: str, keys: tuple[str, ...]) -> bool:
    return any(k in name for k in keys)


def _is_asr(record) -> bool:
    return _ASR_KEY in record["name"]


def _is_tts(record) -> bool:
    return _record_in(record["name"], _TTS_KEYS)


def _is_copy_gen(record) -> bool:
    return _COPY_GEN_KEY in record["name"]


def _is_video_gen(record) -> bool:
    return _record_in(record["name"], _VIDEO_GEN_KEYS)


def _is_other_app(record) -> bool:
    return not (
        _is_asr(record)
        or _is_tts(record)
        or _is_copy_gen(record)
        or _is_video_gen(record)
    )


class _InterceptHandler(logging.Handler):
    """把 stdlib `logging` 的记录转发到 loguru。

    copy_gen 子模块全部用 `logging.getLogger(__name__)`，若不桥接，
    它们的日志只会走 stdlib root handler，不会落到 loguru 的文件 sink，
    也就不会出现在"日志查看器 → 文案生成"中。
    """

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 还原真实调用栈深度，避免所有日志都指向本 handler 行号。
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).bind(
            stdlib_name=record.name
        ).log(level, record.getMessage())


def _install_stdlib_bridge() -> None:
    """全局把 stdlib logging 路由到 loguru。

    幂等：configure_logging 可多次调用（reload 场景），不会叠加 handler。
    """
    root = logging.getLogger()
    # 移除上一次桥接装的 InterceptHandler，避免重复转发
    for h in list(root.handlers):
        if isinstance(h, _InterceptHandler):
            root.removeHandler(h)
    root.addHandler(_InterceptHandler())
    root.setLevel(logging.INFO)
    # 防止 uvicorn / fastapi 等子 logger 自带 handler 又输出一份原文
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "openai"):
        lg = logging.getLogger(noisy)
        lg.handlers = []
        lg.propagate = True


def configure_logging(data_dir: Path | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    if data_dir is not None:
        log_dir = data_dir / "outputs" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # ASR：单独成 sink，debug 级（保留原行为）
        logger.add(
            str(log_dir / "asr_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=_is_asr,
        )
        # TTS：语音生成全部日志（tts_service + api/tts）
        logger.add(
            str(log_dir / "tts_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=_is_tts,
        )
        # 文案生成：copy_gen 服务/路由全部日志（含 prompt body / response body / token）
        logger.add(
            str(log_dir / "copy_gen_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=_is_copy_gen,
        )
        # 视频生成：video_service 全部日志（FFmpeg 命令、探测、转码等）
        logger.add(
            str(log_dir / "video_gen_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="DEBUG",
            filter=_is_video_gen,
        )
        # 系统级 app.log：以上 4 类之外的全部模块
        logger.add(
            str(log_dir / "app_{time:YYYYMMDD_HHmmss}.log"),
            rotation="10 MB",
            encoding="utf-8",
            level="INFO",
            filter=_is_other_app,
        )

    _install_stdlib_bridge()


def get_logger():
    return logger
