from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..utils.logger import get_logger
from .material_service import MatchEvent


logger = get_logger()


@dataclass(frozen=True)
class VideoProbe:
    width: int
    height: int
    duration: float
    has_audio: bool


def _ff_filter_path(path: str) -> str:
    p = Path(path).as_posix()
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p


def probe_video(settings: Settings, video_path: str) -> VideoProbe:
    cmd = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height:format=duration",
        "-of",
        "json",
        video_path,
    ]
    out = subprocess.check_output(
        cmd, text=True, encoding="utf-8", errors="replace", stderr=subprocess.STDOUT
    )
    data = json.loads(out)
    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise RuntimeError("ffprobe 未返回视频流信息")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(data.get("format", {}).get("duration") or 0.0)
    return VideoProbe(
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        duration=max(0.0, duration),
        has_audio=has_audio,
    )


def export_audio_track(
    settings: Settings,
    *,
    video_path: str,
    output_path: str,
    audio_format: str,
) -> None:
    fmt = (audio_format or "").lower()
    if fmt == "wav":
        codec = "pcm_s16le"
    elif fmt == "flac":
        codec = "flac"
    else:
        raise ValueError("audio_format 仅支持 wav 或 flac")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        codec,
        output_path,
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"导出 {fmt} 音轨失败: {proc.stderr.strip() or proc.stdout.strip() or proc.returncode}"
        )


def grid_xy_expr(position: int) -> tuple[str, str]:
    pos = position if 1 <= position <= 9 else 9
    col = (pos - 1) % 3
    row = (pos - 1) // 3
    x_factor = {0: "0", 1: "0.5", 2: "1"}[col]
    y_factor = {0: "0", 1: "0.5", 2: "1"}[row]
    x = f"(main_w-overlay_w)*{x_factor}"
    y = f"(main_h-overlay_h)*{y_factor}"
    return x, y


def resolution_scale(settings_resolution: str) -> tuple[int, int] | None:
    r = (settings_resolution or "").upper()
    if r == "720P":
        return (1280, 720)
    if r == "1080P":
        return (1920, 1080)
    if r == "4K":
        return (3840, 2160)
    return None


def build_ffmpeg_command(
    settings: Settings,
    *,
    video_path: str,
    subtitle_path: str,
    subtitle_encoding: str,
    events: list[MatchEvent],
    output_path: str,
    output_format: str,
    resolution: str,
    video_bitrate_kbps: int,
    add_subtitle_to_video: bool = False,
) -> list[str]:
    success_events = [e for e in events if e.status == "success" and e.material_path]
    video_probe = probe_video(settings, video_path)
    canvas_w, canvas_h = video_probe.width, video_probe.height

    material_to_index: dict[str, int] = {}
    occurrences: dict[str, list[MatchEvent]] = {}
    for event in success_events:
        assert event.material_path is not None
        occurrences.setdefault(event.material_path, []).append(event)

    sound_effect_events = [
        event
        for event in success_events
        if event.sound_effect_path and event.sound_effect_status == "已添加"
    ]
    sound_effect_to_index: dict[str, int] = {}

    cmd: list[str] = [settings.ffmpeg_bin, "-y", "-nostdin", "-i", video_path]

    def _is_image(event: MatchEvent) -> bool:
        return event.material_type == "图片"

    def _is_gif(event: MatchEvent) -> bool:
        return event.material_type == "GIF"

    for material_path, occs in occurrences.items():
        idx = len(material_to_index) + 1
        material_to_index[material_path] = idx

        any_loop = any(item.loop == 1 for item in occs)
        if any(_is_image(item) for item in occs):
            cmd += ["-loop", "1", "-i", material_path]
        elif any(_is_gif(item) for item in occs):
            cmd += ["-ignore_loop", "0", "-i", material_path]
        else:
            if any_loop:
                cmd += ["-stream_loop", "-1", "-i", material_path]
            else:
                cmd += ["-i", material_path]

    for event in sound_effect_events:
        assert event.sound_effect_path is not None
        if event.sound_effect_path in sound_effect_to_index:
            continue
        idx = 1 + len(material_to_index) + len(sound_effect_to_index)
        sound_effect_to_index[event.sound_effect_path] = idx
        cmd += ["-i", event.sound_effect_path]

    filters: list[str] = []
    base_label = "v0"
    filters.append(f"[0:v]setpts=PTS-STARTPTS[{base_label}]")

    overlay_labels: list[tuple[MatchEvent, str]] = []
    for material_path, occs in occurrences.items():
        input_idx = material_to_index[material_path]
        if len(occs) == 1:
            src = f"[{input_idx}:v]"
            branch = f"m{input_idx}_0"
            event = occs[0]
            max_w = max(1, min(canvas_w, int(round(canvas_w * event.size_ratio_percent / 100.0))))
            max_h = max(1, canvas_h)
            filters.append(
                f"{src}setpts=PTS-STARTPTS,format=rgba,"
                f"scale={max_w}:{max_h}:force_original_aspect_ratio=decrease[{branch}]"
            )
            ov = f"ov_{input_idx}_0"
            dur = max(0.01, event.end_time - event.start_time)
            opacity = max(0, min(100, event.opacity)) / 100.0
            filters.append(
                f"[{branch}]trim=duration={dur},setpts=PTS-STARTPTS+{event.start_time}/TB,"
                f"colorchannelmixer=aa={opacity}[{ov}]"
            )
            overlay_labels.append((event, ov))
        else:
            src = f"[{input_idx}:v]"
            base = f"m{input_idx}"
            filters.append(f"{src}setpts=PTS-STARTPTS,format=rgba[{base}]")
            split_outputs = "".join([f"[{base}_{i}]" for i in range(len(occs))])
            filters.append(f"[{base}]split={len(occs)}{split_outputs}")
            for i, event in enumerate(occs):
                ov = f"ov_{input_idx}_{i}"
                dur = max(0.01, event.end_time - event.start_time)
                opacity = max(0, min(100, event.opacity)) / 100.0
                max_w = max(1, min(canvas_w, int(round(canvas_w * event.size_ratio_percent / 100.0))))
                max_h = max(1, canvas_h)
                filters.append(
                    f"[{base}_{i}]scale={max_w}:{max_h}:force_original_aspect_ratio=decrease,"
                    f"trim=duration={dur},setpts=PTS-STARTPTS+{event.start_time}/TB,"
                    f"colorchannelmixer=aa={opacity}[{ov}]"
                )
                overlay_labels.append((event, ov))

    current = base_label
    for i, (event, overlay_label) in enumerate(overlay_labels):
        next_label = f"v{i + 1}"
        x, y = grid_xy_expr(event.position)
        filters.append(
            f"[{current}][{overlay_label}]overlay=x={x}:y={y}:eof_action=pass[{next_label}]"
        )
        current = next_label

    video_output_label = current
    if add_subtitle_to_video:
        subtitle_filter_path = _ff_filter_path(subtitle_path)
        enc = subtitle_encoding or "utf-8"
        filters.append(
            f"[{current}]subtitles='{subtitle_filter_path}':charenc='{enc}'[vout]"
        )
        video_output_label = "vout"

    has_sound_effect = len(sound_effect_events) > 0
    if has_sound_effect:
        if video_probe.has_audio:
            filters.append("[0:a]asetpts=PTS-STARTPTS[a_base]")
        else:
            duration = max(0.1, video_probe.duration)
            filters.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=duration={duration},asetpts=PTS-STARTPTS[a_base]"
            )

        mix_inputs = ["[a_base]"]
        for i, event in enumerate(sound_effect_events):
            assert event.sound_effect_path is not None
            sound_idx = sound_effect_to_index[event.sound_effect_path]
            sound_label = f"ase_{i}"
            duration = max(0.01, event.end_time - event.start_time)
            delay_ms = int(max(0.0, event.start_time) * 1000)
            filters.append(
                f"[{sound_idx}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                f"adelay={delay_ms}:all=1,volume=0.7[{sound_label}]"
            )
            mix_inputs.append(f"[{sound_label}]")
        filters.append(
            f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:"
            "normalize=0:dropout_transition=0[aout]"
        )

    filter_complex = ";".join(filters)
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        f"[{video_output_label}]",
        "-c:v",
        "libx264",
        "-b:v",
        f"{int(video_bitrate_kbps)}k",
    ]

    if has_sound_effect:
        cmd += [
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ]
    else:
        cmd += [
            "-map",
            "0:a?",
            "-c:a",
            "copy",
        ]

    fmt = (output_format or "MP4").upper()
    if fmt == "MOV":
        cmd += ["-f", "mov"]
    else:
        cmd += ["-f", "mp4"]

    cmd.append(output_path)
    return cmd


def run_ffmpeg(
    cmd: list[str],
    log_path: str,
    on_started=None,
    should_stop=None,
    on_tick=None,
    max_run_seconds: float | None = None,
) -> None:
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Running FFmpeg: {}", " ".join(cmd))
    with log_file.open("a", encoding="utf-8") as file_handle:
        file_handle.write("FFmpeg command:\n")
        file_handle.write(" ".join(cmd) + "\n\n")
        process = subprocess.Popen(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=file_handle,
            stderr=file_handle,
            stdin=subprocess.DEVNULL,
        )
        if on_started:
            on_started(process)

        started_at = time.monotonic()
        while process.poll() is None:
            elapsed = time.monotonic() - started_at
            if on_tick:
                try:
                    on_tick(elapsed)
                except Exception:
                    pass

            if max_run_seconds and elapsed > max_run_seconds:
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except Exception:
                        pass
                raise RuntimeError(f"FFmpeg ??????? {int(max_run_seconds)} ?")

            if should_stop and should_stop():
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except Exception:
                        pass
                break

            time.sleep(0.5)

        file_handle.write("\n")
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg ???????? {process.returncode}")
