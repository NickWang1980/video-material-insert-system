"""FFmpeg hardware video encoder detection and argument builder.

Resolves a user-selected encoder mode (auto/cpu/cuda/qsv/amf) to the actual
ffmpeg codec name and quality control arguments, with automatic fallback to
libx264 when the requested hardware encoder is not available.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

ENCODER_AUTO_ORDER = ("nvenc", "qsv", "amf")

# Map normalized preset names (libx264 vocabulary) to per-codec preset values.
_PRESET_MAP = {
    "libx264": {
        "ultrafast": "ultrafast", "superfast": "superfast",
        "veryfast": "veryfast", "faster": "faster",
        "fast": "fast", "medium": "medium",
    },
    "h264_nvenc": {
        "ultrafast": "p1", "superfast": "p1",
        "veryfast": "p2", "faster": "p3",
        "fast": "p4", "medium": "p4",
    },
    "h264_qsv": {
        "ultrafast": "veryfast", "superfast": "veryfast",
        "veryfast": "faster", "faster": "faster",
        "fast": "fast", "medium": "medium",
    },
    "h264_amf": {
        "ultrafast": "speed", "superfast": "speed",
        "veryfast": "speed", "faster": "speed",
        "fast": "balanced", "medium": "balanced",
    },
}


@lru_cache(maxsize=1)
def list_available_hw_encoders(ffmpeg_bin: str) -> frozenset[str]:
    """Probe ffmpeg for which hardware encoders are compiled in.

    Returns a set of short keys (subset of {"nvenc", "qsv", "amf"}).
    Cached: probed once per process.
    """
    try:
        out = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return frozenset()
    found: set[str] = set()
    if "h264_nvenc" in out:
        found.add("nvenc")
    if "h264_qsv" in out:
        found.add("qsv")
    if "h264_amf" in out:
        found.add("amf")
    return frozenset(found)


def _pick_codec(mode: str, ffmpeg_bin: str) -> str:
    mode = (mode or "auto").lower()
    avail = list_available_hw_encoders(ffmpeg_bin)
    if mode == "auto":
        for c in ENCODER_AUTO_ORDER:
            if c in avail:
                return f"h264_{c}"
        return "libx264"
    if mode in ("cuda", "nvenc") and "nvenc" in avail:
        return "h264_nvenc"
    if mode == "qsv" and "qsv" in avail:
        return "h264_qsv"
    if mode == "amf" and "amf" in avail:
        return "h264_amf"
    return "libx264"


def build_video_encode_args(
    mode: str,
    ffmpeg_bin: str,
    *,
    preset: str = "veryfast",
    crf: int | None = 23,
    bitrate_kbps: int | None = None,
) -> list[str]:
    """Return ffmpeg args for video encoding.

    Sample output: ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-rc", "vbr"].
    Bitrate (when given) takes priority over CRF — both are translated to
    codec-appropriate flags (NVENC `-cq`, QSV `-global_quality`, AMF `-qp_*`).
    """
    codec = _pick_codec(mode, ffmpeg_bin)
    args = ["-c:v", codec, "-preset", _PRESET_MAP[codec].get(preset, "medium")]

    if bitrate_kbps:
        args += ["-b:v", f"{int(bitrate_kbps)}k"]
        if codec == "h264_nvenc":
            args += ["-rc", "vbr"]
        return args

    if crf is None:
        return args

    if codec == "libx264":
        args += ["-crf", str(crf)]
    elif codec == "h264_nvenc":
        args += ["-cq", str(crf), "-rc", "vbr"]
    elif codec == "h264_qsv":
        args += ["-global_quality", str(crf)]
    elif codec == "h264_amf":
        args += ["-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)]
    return args


def get_active_codec(mode: str, ffmpeg_bin: str) -> str:
    """Return the actual codec name that would be used (for logging/UI)."""
    return _pick_codec(mode, ffmpeg_bin)
