"""手机边框 PNG 的处理：去掉纯色背景 + 抠掉纯色屏幕，只留手机边框，并给出屏幕矩形。

手机边框画中画里，边框 PNG 叠在视频上层；要让视频透出来、且只显示"手机本体"，需要：
  - 把手机轮廓**外的纯色背景**抠成透明（否则四周会盖住源视频）；
  - 把中间的**屏幕**抠成透明（视频从这里透出来）；
  - **保留黑色边框本体**（含刘海/灵动岛等内部不透明元素）。

做法（detect_screen_rect）：用 Pillow 在**原分辨率**做 flood fill（RGBA 感知，连通+颜色容差）：
  1. 从四个角 flood fill → 手机外的背景区（背景与屏幕即便同色，也被中间黑边框隔开，不会串）。
  2. 从中心 flood fill → 屏幕区（被黑边框包住，取其 bbox 作屏幕矩形）。
  3. 把背景区 + 屏幕区的 alpha 置 0，保存为 {stem}.cut.png；黑边框因色差/alpha 差被保留。
  4. 守卫：背景区若侵入屏幕周边（说明边框被吃掉/无背景）则放弃去背景；屏幕无效则兜底内缩。

结果写同名 .rect.json sidecar 缓存。overlay_file 即实际要叠加的（已抠好的）图。
"""

from __future__ import annotations

import json
from pathlib import Path

from .logger import get_logger

logger = get_logger()

# 透明判定阈值（alpha 低于此值算透明）。
_ALPHA_THRESHOLD = 16
# flood fill 颜色容差（RGBA 各通道绝对差之和；含 alpha，故透明区与不透明边框天然不串）。
_FLOOD_TOL = 24
# 兜底内缩比例。
_FALLBACK_INSET = 0.06
# 屏幕有效面积占比范围。
_AREA_MIN_FRAC = 0.03
_AREA_MAX_FRAC = 0.96

_CUT_SUFFIX = ".cut.png"
_MARK_BG = (1, 254, 2, 255)
_MARK_SCREEN = (254, 1, 253, 255)
# 抠图算法版本：升级算法后递增，旧 sidecar 失配即自动重算（让既有边框也吃到修复，无需重传）。
_CACHE_VERSION = 2


def _sidecar_path(p: Path) -> Path:
    return p.with_suffix(p.suffix + ".rect.json")


def _cut_path(p: Path) -> Path:
    return p.with_name(p.stem + _CUT_SUFFIX)


def _mask_eq(arr, mark) -> "any":
    return (arr[..., 0] == mark[0]) & (arr[..., 1] == mark[1]) & (arr[..., 2] == mark[2])


# 去背景后收边/羽化参数。
_EDGE_DILATE = 2   # 背景去除区向外膨胀几像素，吃掉边框外侧残留的抗锯齿灰边。
_EDGE_FEATHER = 1.0  # 高斯羽化半径，做平滑抗锯齿边。


def _feather_remove(remove, dilate, feather):
    """把布尔"抠除区"按 dilate(膨胀像素，0=不膨胀)+feather(高斯羽化)处理，返回 0~1 抠除强度图。"""
    from PIL import Image, ImageFilter
    import numpy as np

    m = Image.fromarray((remove.astype(np.uint8)) * 255, "L")
    if dilate > 0:
        m = m.filter(ImageFilter.MaxFilter(2 * dilate + 1))   # 膨胀抠除区
    if feather > 0:
        m = m.filter(ImageFilter.GaussianBlur(feather))       # 羽化
    return np.asarray(m, dtype=np.float32) / 255.0


def _compute_screen_rect(png_path: Path) -> dict:
    from PIL import Image, ImageDraw
    import numpy as np

    with Image.open(png_path) as raw:
        im = raw.convert("RGBA")
    fw, fh = im.size
    work = im.copy()

    # 1) 去背景：从四角 flood fill。
    corners = [(0, 0), (fw - 1, 0), (0, fh - 1), (fw - 1, fh - 1)]
    for cxy in corners:
        if work.getpixel(cxy)[:3] == _MARK_BG[:3]:
            continue  # 已被前一个角填过
        try:
            ImageDraw.floodfill(work, cxy, _MARK_BG, thresh=_FLOOD_TOL)
        except Exception:
            pass

    # 2) 抠屏幕：从中心 flood fill（中心若已被当背景填了，说明无独立屏幕）。
    cx, cy = fw // 2, fh // 2
    center_is_bg = work.getpixel((cx, cy))[:3] == _MARK_BG[:3]
    if not center_is_bg:
        try:
            ImageDraw.floodfill(work, (cx, cy), _MARK_SCREEN, thresh=_FLOOD_TOL)
        except Exception:
            pass

    aw = np.array(work)
    bg_mask = _mask_eq(aw, _MARK_BG)
    screen_mask = _mask_eq(aw, _MARK_SCREEN)

    # 屏幕有效性
    rect = None
    screen_valid = False
    if screen_mask.any():
        ys, xs = np.where(screen_mask)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        touches = x0 == 0 or y0 == 0 or x1 == fw - 1 or y1 == fh - 1
        frac = float(screen_mask.sum()) / (fw * fh)
        if (not touches) and (_AREA_MIN_FRAC <= frac <= _AREA_MAX_FRAC):
            rect = [x0, y0, x1 - x0 + 1, y1 - y0 + 1]
            screen_valid = True

    arr = np.array(im)

    # 去背景守卫：只在"去背景后还剩下足够的不透明边框"时才去。
    # 防的是"边框贴边、四角即边框本体"被整片当背景吃掉的情况（那会把整个手机抹掉）。
    bg_valid = bool(bg_mask.any())
    if bg_valid:
        kept = (~bg_mask) & (~screen_mask) & (arr[..., 3] > _ALPHA_THRESHOLD)
        if int(kept.sum()) < 0.005 * fw * fh:
            bg_valid = False
            logger.warning("[phone_frame] 去背景会抹掉手机本体，放弃去背景 frame={}", png_path.name)
    method = "fallback"
    detected = False
    screen_remove = np.zeros((fh, fw), dtype=bool)
    if screen_valid:
        screen_remove |= screen_mask
        method = "color"
        detected = True
    else:
        # 兜底：内缩矩形当屏幕。
        iw, ih = int(round(fw * _FALLBACK_INSET)), int(round(fh * _FALLBACK_INSET))
        rect = [iw, ih, max(1, fw - 2 * iw), max(1, fh - 2 * ih)]
        x, y, w, h = rect
        screen_remove[y : y + h, x : x + w] = True

    # 抗毛边 / 防溢出：硬切只删接近背景/屏幕色的像素，边框边缘会残留一圈抗锯齿浅灰。
    #  · 背景去除区向【外】膨胀(+_EDGE_DILATE)，吃掉边框外侧那圈灰毛边；
    #  · 屏幕透明孔【不膨胀】——一旦把孔向外撑大，孔沿就会越过黑边框内沿，
    #    素材便从边框下露出，造成"轻微溢出"手机范围（本次修复点）。
    # 两者各自羽化为 0~1 抠除强度后相乘叠到原 alpha 上（羽化带落在黑边框上，无灰晕）。
    keep = 1.0 - _feather_remove(screen_remove, 0, _EDGE_FEATHER)
    if bg_valid:
        keep = keep * (1.0 - _feather_remove(bg_mask, _EDGE_DILATE, _EDGE_FEATHER))
    arr[..., 3] = np.clip(arr[..., 3].astype(np.float32) * keep, 0, 255).astype(np.uint8)

    from PIL import Image as _Image

    cut = _cut_path(png_path)
    _Image.fromarray(arr, "RGBA").save(cut)

    # 手机本体 bbox = 去背景后剩余的不透明区（边框）外接矩形。缩放时按它定百分比，
    # 这样百分比是相对"手机本体"，不受原图透明边距大小影响。
    opaque = arr[..., 3] > _ALPHA_THRESHOLD
    if opaque.any():
        oys, oxs = np.where(opaque)
        content_bbox = [
            int(oxs.min()), int(oys.min()),
            int(oxs.max() - oxs.min() + 1), int(oys.max() - oys.min() + 1),
        ]
    else:
        content_bbox = [0, 0, fw, fh]

    logger.info(
        "[phone_frame] frame={} {}x{} method={} bg_removed={} rect={} content={} -> {}",
        png_path.name, fw, fh, method, bg_valid, rect, content_bbox, cut.name,
    )
    return {
        "frame_w": fw, "frame_h": fh, "screen": rect, "content_bbox": content_bbox,
        "detected": detected, "method": method, "overlay_file": cut.name,
        "bg_removed": bg_valid, "cache_version": _CACHE_VERSION,
    }


def detect_screen_rect(png_path: str | Path, *, refresh: bool = False) -> dict:
    """识别（或读缓存）手机边框的屏幕矩形，并产出"已去背景+抠屏幕"的叠加图。

    返回 {frame_w, frame_h, screen:[x,y,w,h], detected, method, overlay_file, bg_removed}。
    method: "color"(识别到屏幕) | "fallback"(未识别,内缩兜底)。
    overlay_file: 实际要 overlay 的（已抠好的）文件名 {stem}.cut.png。
    """
    path = Path(png_path)
    sidecar = _sidecar_path(path)

    if not refresh and sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            ok = (
                isinstance(data, dict)
                and data.get("cache_version") == _CACHE_VERSION
                and isinstance(data.get("screen"), list)
                and len(data["screen"]) == 4
                and "overlay_file" in data
                and isinstance(data.get("content_bbox"), list)
            )
            if ok and path.with_name(data["overlay_file"]).exists():
                return data
        except (json.JSONDecodeError, OSError):
            pass

    result = _compute_screen_rect(path)
    try:
        sidecar.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("[phone_frame] sidecar 写入失败 {}: {}", sidecar.name, exc)
    return result
