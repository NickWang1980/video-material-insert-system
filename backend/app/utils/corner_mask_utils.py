"""圆角画中画用的遮罩 / 描边框 PNG 生成与缓存。

设计见 docs/20260603_*_圆角画中画素材插入实施记录.md：
- 给定素材在画布上的精确像素尺寸 (ow, oh)，生成一张白色抗锯齿圆角矩形 alpha 遮罩，
  供 FFmpeg `alphamerge` 把素材四角切成圆角。
- 若描边粗细 > 0，再生成一张「透明底 + 描边色圆角描边框（中心透明）」的 RGBA PNG，
  供 FFmpeg `overlay` 叠在圆角素材上方。
- 同一组参数只生成一次，按文件名缓存到 data/cache/pip_masks/。

不引入逐帧 geq；遮罩仅按尺寸生成一次，后续命中缓存。
"""

from __future__ import annotations

from pathlib import Path

from ..config import Settings

# 抗锯齿超采样倍数：先在 N 倍尺寸绘制，再 LANCZOS 降采样到目标尺寸。
_SUPERSAMPLE = 4


def _normalize_hex(color: str | None) -> str:
    """把任意颜色输入规整成 6 位大写十六进制（不带 #）。非法值兜底为白色。"""
    c = (color or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        return "FFFFFF"
    return c.upper()


def _cache_dir(settings: Settings) -> Path:
    d = settings.data_dir / "cache" / "pip_masks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_corner_assets(
    settings: Settings,
    overlay_w: int,
    overlay_h: int,
    radius_px: int,
    border_w_px: int,
    border_color: str,
) -> tuple[str, str | None]:
    """返回 (圆角 alpha 遮罩 PNG 路径, 描边框 PNG 路径或 None)。

    overlay_w/overlay_h：素材在画布上缩放后的精确像素尺寸（必须与 FFmpeg scale 结果一致）。
    radius_px：圆角半径（会被裁剪到不超过较短边的一半）。
    border_w_px：描边粗细，<=0 时第二个返回值为 None。
    border_color：描边颜色（十六进制，可带或不带 #）。
    """
    from PIL import Image, ImageDraw

    ow = max(1, int(overlay_w))
    oh = max(1, int(overlay_h))
    radius = max(0, int(radius_px))
    radius = min(radius, min(ow, oh) // 2)
    border_w = max(0, int(border_w_px))
    color_hex = _normalize_hex(border_color)

    cache_dir = _cache_dir(settings)
    ss = _SUPERSAMPLE

    # 1) 圆角 alpha 遮罩（灰度，与描边颜色无关，可跨规则复用）
    mask_path = cache_dir / f"mask_{ow}x{oh}_r{radius}.png"
    if not mask_path.exists():
        big = Image.new("L", (ow * ss, oh * ss), 0)
        draw = ImageDraw.Draw(big)
        draw.rounded_rectangle(
            [0, 0, ow * ss - 1, oh * ss - 1],
            radius=radius * ss,
            fill=255,
        )
        big.resize((ow, oh), Image.LANCZOS).save(mask_path)

    # 2) 描边框（RGBA，透明底 + 圆角描边，中心透明）
    border_path: str | None = None
    if border_w > 0:
        bpath = cache_dir / f"border_{ow}x{oh}_r{radius}_b{border_w}_{color_hex}.png"
        if not bpath.exists():
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
            big = Image.new("RGBA", (ow * ss, oh * ss), (0, 0, 0, 0))
            draw = ImageDraw.Draw(big)
            # 描边沿矩形路径居中绘制：路径内缩 border_w/2，使描边外缘与圆角外缘对齐，
            # 对应外半径 = radius，故路径半径 = radius - border_w/2。
            inset = border_w * ss / 2.0
            path_radius = max(0.0, (radius - border_w / 2.0)) * ss
            draw.rounded_rectangle(
                [inset, inset, ow * ss - 1 - inset, oh * ss - 1 - inset],
                radius=path_radius,
                outline=(r, g, b, 255),
                width=max(1, border_w * ss),
            )
            big.resize((ow, oh), Image.LANCZOS).save(bpath)
        border_path = str(bpath)

    return str(mask_path), border_path
