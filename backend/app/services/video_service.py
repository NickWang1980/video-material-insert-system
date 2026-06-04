from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..utils.corner_mask_utils import get_corner_assets
from ..utils.encoder_utils import build_video_encode_args
from ..utils.logger import get_logger
from ..utils.phone_frame_utils import detect_screen_rect
from .material_service import MatchEvent


logger = get_logger()


@dataclass(frozen=True)
class VideoProbe:
    width: int
    height: int
    duration: float
    has_audio: bool


def _ff_filter_path(path: str) -> str:
    value = Path(path).as_posix()
    if len(value) >= 2 and value[1] == ":":
        value = value[0] + "\\:" + value[2:]
    return value


def probe_video(settings: Settings, video_path: str) -> VideoProbe:
    logger.info("[video_gen] probe_video path={}", video_path)
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
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video_stream:
        logger.error("[video_gen] probe_video: ffprobe 未返回视频流信息 path={}", video_path)
        raise RuntimeError("ffprobe 未返回视频流信息")
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    duration = float(data.get("format", {}).get("duration") or 0.0)
    probe = VideoProbe(
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        duration=max(0.0, duration),
        has_audio=has_audio,
    )
    logger.info(
        "[video_gen] probe_video ok {}x{} dur={:.2f}s audio={}",
        probe.width, probe.height, probe.duration, probe.has_audio,
    )
    return probe


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
    logger.info(
        "[video_gen] export_audio_track src={} dst={} fmt={}",
        video_path, output_path, fmt,
    )
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
        err = proc.stderr.strip() or proc.stdout.strip() or str(proc.returncode)
        logger.error("[video_gen] export_audio_track failed fmt={} err={}", fmt, err)
        raise RuntimeError(f"导出 {fmt} 音轨失败: {err}")
    logger.info("[video_gen] export_audio_track ok dst={}", output_path)


def strip_video_audio(
    settings: Settings,
    *,
    input_path: str,
    output_path: str,
    video_encoder_mode: str = "auto",
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "[video_gen] strip_video_audio src={} dst={} encoder_mode={}",
        input_path, output_path, video_encoder_mode,
    )
    cmd_copy = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        input_path,
        "-an",
        "-c:v",
        "copy",
        output_path,
    ]
    proc_copy = subprocess.run(
        cmd_copy,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc_copy.returncode == 0:
        logger.info("[video_gen] strip_video_audio ok via stream copy dst={}", output_path)
        return
    logger.warning(
        "[video_gen] strip_video_audio stream-copy failed (rc={}), retry with re-encode",
        proc_copy.returncode,
    )

    cmd_reencode = [
        settings.ffmpeg_bin, "-y", "-i", input_path, "-an",
        *build_video_encode_args(
            video_encoder_mode, settings.ffmpeg_bin, preset="veryfast", crf=23
        ),
        output_path,
    ]
    proc_reencode = subprocess.run(
        cmd_reencode,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc_reencode.returncode != 0:
        message = (
            proc_reencode.stderr.strip()
            or proc_reencode.stdout.strip()
            or proc_copy.stderr.strip()
            or proc_copy.stdout.strip()
            or str(proc_reencode.returncode)
        )
        logger.error("[video_gen] strip_video_audio re-encode failed err={}", message)
        raise RuntimeError(f"视频去音轨失败: {message}")
    logger.info("[video_gen] strip_video_audio ok via re-encode dst={}", output_path)


def grid_xy_expr(position: int) -> tuple[str, str]:
    pos = position if 1 <= position <= 9 else 9
    col = (pos - 1) % 3
    row = (pos - 1) // 3
    x_factor = {0: "0.25", 1: "0.5", 2: "0.75"}[col]
    y_factor = {0: "0.25", 1: "0.5", 2: "0.75"}[row]
    x = f"(main_w-overlay_w)*{x_factor}"
    y = f"(main_h-overlay_h)*{y_factor}"
    return x, y


def resolution_scale(settings_resolution: str) -> tuple[int, int] | None:
    value = (settings_resolution or "").upper()
    if value == "720P":
        return (1280, 720)
    if value == "1080P":
        return (1920, 1080)
    if value == "4K":
        return (3840, 2160)
    return None


def _clip_duration(event: MatchEvent) -> float:
    if event.video_duration_seconds and event.video_duration_seconds > 0:
        return float(event.video_duration_seconds)
    return max(0.01, event.end_time - event.start_time)


def _apply_collision_layer_order(
    overlay_labels: list[tuple[MatchEvent, str]],
) -> list[tuple[MatchEvent, str]]:
    if len(overlay_labels) <= 1:
        return overlay_labels

    grouped: dict[int, list[tuple[int, MatchEvent, str]]] = {}
    for idx, (event, overlay_label) in enumerate(overlay_labels):
        if event.subtitle_index <= 0 or event.layer_rank is None:
            continue
        grouped.setdefault(event.subtitle_index, []).append((idx, event, overlay_label))

    if not grouped:
        return overlay_labels

    reordered = list(overlay_labels)
    for items in grouped.values():
        if len(items) <= 1:
            continue

        slots = sorted(item[0] for item in items)
        # layer_rank 越小优先级越高；渲染时高层应最后 overlay，所以这里按降序排。
        ordered = sorted(
            items,
            key=lambda item: (-(item[1].layer_rank or 0), item[0]),
        )
        for slot, (_, event, overlay_label) in zip(slots, ordered):
            reordered[slot] = (event, overlay_label)

    return reordered


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
    video_encoder_mode: str = "auto",
) -> list[str]:
    success_events = [event for event in events if event.status == "success" and event.material_path]
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

    def _is_video(event: MatchEvent) -> bool:
        return event.material_type == "短视频"

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

    # ── 圆角画中画：探测素材尺寸 + 预生成圆角遮罩/描边 PNG，并注册为额外输入 ──
    # 遮罩按精确缩放尺寸生成（与下面的 scale=ow:oh 完全一致），否则 alphamerge 会因
    # 尺寸不符报错。普通画中画完全不进这段逻辑。
    mask_to_index: dict[str, int] = {}
    event_corner_info: dict[int, dict[str, object]] = {}
    _native_size_cache: dict[str, tuple[int, int]] = {}

    def _native_size(path: str) -> tuple[int, int]:
        if path not in _native_size_cache:
            try:
                mp = probe_video(settings, path)
                _native_size_cache[path] = (max(1, mp.width), max(1, mp.height))
            except Exception:
                # 探测失败时退化到画布尺寸，至少保证 scale 不报错。
                _native_size_cache[path] = (canvas_w, canvas_h)
        return _native_size_cache[path]

    def _scaled_dims(event: MatchEvent) -> tuple[int, int]:
        assert event.material_path is not None
        max_w = max(1, min(canvas_w, int(round(canvas_w * event.size_ratio_percent / 100.0))))
        max_h = max(1, canvas_h)
        nw, nh = _native_size(event.material_path)
        s = min(max_w / nw, max_h / nh)
        return max(1, int(round(nw * s))), max(1, int(round(nh * s)))

    def _is_rounded(event: MatchEvent) -> bool:
        if getattr(event, "corner_style", "普通") != "圆角":
            return False
        radius = max(0, int(getattr(event, "corner_radius_px", 0) or 0))
        border_w = max(0, int(getattr(event, "border_width_px", 0) or 0))
        return radius > 0 or border_w > 0

    for event in success_events:
        if not _is_rounded(event):
            continue
        radius = max(0, int(getattr(event, "corner_radius_px", 0) or 0))
        border_w = max(0, int(getattr(event, "border_width_px", 0) or 0))
        ow, oh = _scaled_dims(event)
        mask_png, border_png = get_corner_assets(
            settings, ow, oh, radius, border_w, getattr(event, "border_color", "#FFFFFF")
        )
        event_corner_info[id(event)] = {
            "ow": ow,
            "oh": oh,
            "mask": mask_png,
            "border": border_png,
        }

    # ── 手机边框画中画：解析上传的边框 PNG、识别屏幕透明区、算出框与屏幕的缩放尺寸 ──
    event_phone_info: dict[int, dict[str, object]] = {}

    def _phone_frame_path(event: MatchEvent) -> str | None:
        if getattr(event, "corner_style", "普通") != "手机边框":
            return None
        name = (getattr(event, "phone_frame_file", "") or "").strip()
        if not name:
            return None
        path = settings.data_dir / "uploads" / "phone_frames" / Path(name).name
        return str(path) if path.exists() else None

    for event in success_events:
        frame_path = _phone_frame_path(event)
        if not frame_path:
            continue
        try:
            rect = detect_screen_rect(frame_path)
        except Exception:
            logger.warning("[phone_frame] 识别失败，回退普通画中画 file={}", frame_path)
            continue
        fw = max(1, int(rect.get("frame_w") or 1))
        fh = max(1, int(rect.get("frame_h") or 1))
        sx, sy, sw_screen, sh_screen = (rect.get("screen") or [0, 0, fw, fh])
        # 实际叠加用的边框图：alpha→原图；纯色/兜底→已抠透明的 cut 图。
        overlay_name = str(rect.get("overlay_file") or Path(frame_path).name)
        overlay_path = Path(frame_path).with_name(overlay_name)
        if not overlay_path.exists():
            overlay_path = Path(frame_path)  # cut 图丢失则退回原图
        # 按「手机本体(content_bbox=去背景后剩余的不透明边框) contain 适配画布 × 百分比」缩放：
        # 百分比相对源视频整屏，100% = 手机本体铺满视频（占满绑定边），75% = 占 3/4。
        # 不再用整张原图尺寸，故不受原图透明边距影响。
        content = rect.get("content_bbox") or [0, 0, fw, fh]
        bw = max(1, int(content[2]))
        bh = max(1, int(content[3]))
        ratio = max(1.0, float(event.size_ratio_percent)) / 100.0
        s = min(canvas_w / bw, canvas_h / bh) * ratio
        ow = max(1, int(round(fw * s)))
        oh = max(1, int(round(fh * s)))
        # 屏幕矩形按同比例缩放并夹取到框内。
        rx = max(0, min(int(round(sx * ow / fw)), ow - 1))
        ry = max(0, min(int(round(sy * oh / fh)), oh - 1))
        rw = max(1, min(int(round(sw_screen * ow / fw)), ow - rx))
        rh = max(1, min(int(round(sh_screen * oh / fh)), oh - ry))
        # 图片素材若按屏幕宽度铺满后比屏幕高 → 自动竖向滚动（长截图效果）；视频不滚动。
        scroll = False
        img_h = rh
        if _is_image(event):
            nw, nh = _native_size(event.material_path)
            img_h = max(rh, int(round(rw * nh / nw)))
            scroll = img_h > rh + 1
        event_phone_info[id(event)] = {
            "ow": ow, "oh": oh, "rx": rx, "ry": ry, "rw": rw, "rh": rh,
            "scroll": scroll, "img_h": img_h, "frame": str(overlay_path),
        }

    # 遮罩/描边/边框 PNG 的输入索引必须排在 materials + 音效之后，避免打乱既有引用。
    next_input_idx = 1 + len(material_to_index) + len(sound_effect_to_index)
    for info in event_corner_info.values():
        for key in ("mask", "border"):
            png = info[key]
            if png and png not in mask_to_index:
                mask_to_index[png] = next_input_idx
                cmd += ["-loop", "1", "-i", str(png)]
                next_input_idx += 1
    for info in event_phone_info.values():
        png = info["frame"]
        if png and png not in mask_to_index:
            mask_to_index[png] = next_input_idx
            cmd += ["-loop", "1", "-i", str(png)]
            next_input_idx += 1

    def _scale_fragment(event: MatchEvent) -> str:
        pinfo = event_phone_info.get(id(event))
        if pinfo:
            rw, rh, ow, oh, rx, ry = (
                pinfo["rw"], pinfo["rh"], pinfo["ow"], pinfo["oh"], pinfo["rx"], pinfo["ry"]
            )
            if pinfo.get("scroll"):
                # 长图：按屏幕宽铺满后竖向自动滚动（crop 的 y 用时间表达式，0→底部）。
                ih = pinfo["img_h"]
                dur = max(0.01, event.end_time - event.start_time)
                y_expr = f"(({ih}-{rh})*min(t/{dur:.3f}\\,1))"
                return (
                    f"scale={rw}:{ih},"
                    f"crop={rw}:{rh}:0:{y_expr},"
                    f"pad={ow}:{oh}:{rx}:{ry}:color=black@0"
                )
            # 手机边框：素材 cover 裁切到屏幕尺寸，再 pad 到屏幕位置（透明底）。
            return (
                f"scale={rw}:{rh}:force_original_aspect_ratio=increase,"
                f"crop={rw}:{rh},"
                f"pad={ow}:{oh}:{rx}:{ry}:color=black@0"
            )
        info = event_corner_info.get(id(event))
        if info:
            # 圆角：精确缩放到遮罩尺寸，保证 alphamerge 尺寸一致。
            return f"scale={info['ow']}:{info['oh']}"
        max_w = max(1, min(canvas_w, int(round(canvas_w * event.size_ratio_percent / 100.0))))
        max_h = max(1, canvas_h)
        return f"scale={max_w}:{max_h}:force_original_aspect_ratio=decrease"

    def _emit_corner(in_label: str, event: MatchEvent, tag: str) -> str:
        """追加圆角(alphamerge+描边) 或 手机边框(overlay 边框) 子链，返回新 label；普通原样返回。"""
        pinfo = event_phone_info.get(id(event))
        if pinfo:
            # 把边框 PNG 缩到整框尺寸后叠在已 pad 好的素材上层。
            frame_idx = mask_to_index[pinfo["frame"]]
            frm = f"pff_{tag}"
            filters.append(f"[{frame_idx}:v]scale={pinfo['ow']}:{pinfo['oh']}[{frm}]")
            out_label = f"pf_{tag}"
            filters.append(f"[{in_label}][{frm}]overlay=0:0:shortest=1[{out_label}]")
            return out_label
        info = event_corner_info.get(id(event))
        if not info:
            return in_label
        mask_idx = mask_to_index[info["mask"]]
        out_label = f"mr_{tag}"
        filters.append(f"[{in_label}][{mask_idx}:v]alphamerge=shortest=1[{out_label}]")
        if info["border"]:
            border_idx = mask_to_index[info["border"]]
            border_label = f"mb_{tag}"
            filters.append(
                f"[{out_label}][{border_idx}:v]overlay=0:0:shortest=1[{border_label}]"
            )
            out_label = border_label
        return out_label

    overlay_labels: list[tuple[MatchEvent, str]] = []
    for material_path, occs in occurrences.items():
        input_idx = material_to_index[material_path]
        if len(occs) == 1:
            src = f"[{input_idx}:v]"
            branch = f"m{input_idx}_0"
            event = occs[0]
            scale_frag = _scale_fragment(event)
            if _is_video(event):
                clip_duration = _clip_duration(event)
                clip_start = max(0.0, event.video_start_seconds)
                filters.append(
                    f"{src}trim=start={clip_start}:duration={clip_duration},setpts=PTS-STARTPTS,"
                    f"format=rgba,{scale_frag}[{branch}]"
                )
            else:
                filters.append(
                    f"{src}setpts=PTS-STARTPTS,format=rgba,"
                    f"{scale_frag}[{branch}]"
                )

            rounded = _emit_corner(branch, event, f"{input_idx}_0")
            ov = f"ov_{input_idx}_0"
            overlay_duration = max(0.01, event.end_time - event.start_time)
            opacity = max(0, min(100, event.opacity)) / 100.0
            filters.append(
                f"[{rounded}]trim=duration={overlay_duration},setpts=PTS-STARTPTS+{event.start_time}/TB,"
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
                sc = f"sc_{input_idx}_{i}"
                overlay_duration = max(0.01, event.end_time - event.start_time)
                opacity = max(0, min(100, event.opacity)) / 100.0
                scale_frag = _scale_fragment(event)
                if _is_video(event):
                    clip_duration = _clip_duration(event)
                    clip_start = max(0.0, event.video_start_seconds)
                    filters.append(
                        f"[{base}_{i}]trim=start={clip_start}:duration={clip_duration},setpts=PTS-STARTPTS,"
                        f"{scale_frag}[{sc}]"
                    )
                else:
                    filters.append(f"[{base}_{i}]{scale_frag}[{sc}]")
                rounded = _emit_corner(sc, event, f"{input_idx}_{i}")
                filters.append(
                    f"[{rounded}]trim=duration={overlay_duration},setpts=PTS-STARTPTS+{event.start_time}/TB,"
                    f"colorchannelmixer=aa={opacity}[{ov}]"
                )
                overlay_labels.append((event, ov))

    overlay_labels = _apply_collision_layer_order(overlay_labels)

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
        encoding = subtitle_encoding or "utf-8"
        filters.append(f"[{current}]subtitles='{subtitle_filter_path}':charenc='{encoding}'[vout]")
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
        *build_video_encode_args(
            video_encoder_mode,
            settings.ffmpeg_bin,
            preset="veryfast",
            bitrate_kbps=int(video_bitrate_kbps),
        ),
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
    logger.info("[video_gen] Running FFmpeg: {}", " ".join(cmd))
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
                raise RuntimeError(f"FFmpeg 运行超时（>{int(max_run_seconds)} 秒）")

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
            logger.error(
                "[video_gen] FFmpeg exit rc={} log={}", process.returncode, log_path
            )
            raise RuntimeError(f"FFmpeg 执行失败，返回码 {process.returncode}")
    logger.info("[video_gen] FFmpeg done rc=0 log={}", log_path)
