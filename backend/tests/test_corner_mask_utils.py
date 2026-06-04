from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.app.utils.corner_mask_utils import _normalize_hex, get_corner_assets


class _Settings:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir


def test_normalize_hex_variants():
    assert _normalize_hex("#ff0000") == "FF0000"
    assert _normalize_hex("0f0") == "00FF00"
    assert _normalize_hex("white") == "FFFFFF"  # 非法 → 兜底白
    assert _normalize_hex(None) == "FFFFFF"


def test_get_corner_assets_mask_only(tmp_path):
    settings = _Settings(tmp_path)
    mask, border = get_corner_assets(settings, 324, 576, 30, 0, "#FFFFFF")
    assert border is None
    assert Path(mask).exists()
    with Image.open(mask) as im:
        assert im.size == (324, 576)


def test_get_corner_assets_with_border(tmp_path):
    settings = _Settings(tmp_path)
    mask, border = get_corner_assets(settings, 200, 200, 20, 4, "#00FF00")
    assert Path(mask).exists()
    assert border is not None and Path(border).exists()
    with Image.open(border) as im:
        assert im.size == (200, 200)
        assert im.mode == "RGBA"


def test_get_corner_assets_cached(tmp_path):
    settings = _Settings(tmp_path)
    mask1, _ = get_corner_assets(settings, 100, 100, 10, 0, "#FFFFFF")
    mtime1 = Path(mask1).stat().st_mtime_ns
    mask2, _ = get_corner_assets(settings, 100, 100, 10, 0, "#FFFFFF")
    # 命中缓存：同路径且未被重写。
    assert mask1 == mask2
    assert Path(mask2).stat().st_mtime_ns == mtime1


def test_radius_clamped_to_half_min_dim(tmp_path):
    settings = _Settings(tmp_path)
    # 半径 9999 会被裁剪到 min(w,h)//2 = 50；文件名应反映裁剪后的半径。
    mask, _ = get_corner_assets(settings, 100, 120, 9999, 0, "#FFFFFF")
    assert "_r50" in Path(mask).name
