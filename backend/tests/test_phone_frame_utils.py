from __future__ import annotations

from PIL import Image

from backend.app.utils.phone_frame_utils import detect_screen_rect


# 用较厚的边框(bezel 12 → screen 60，边框 ~48px)，避免羽化波及"深处边框"点的断言。
def _frame(path, w=240, h=440, bezel=12, screen_inset=60,
           bg=(0, 0, 0, 0), bezel_rgb=(10, 10, 10), screen=(255, 255, 255, 255)):
    """造手机边框：外部=bg，边框=bezel_rgb(不透明)，屏幕=screen。"""
    im = Image.new("RGBA", (w, h), bg)
    px = im.load()
    for y in range(bezel, h - bezel):
        for x in range(bezel, w - bezel):
            px[x, y] = (*bezel_rgb, 255)
    for y in range(screen_inset, h - screen_inset):
        for x in range(screen_inset, w - screen_inset):
            px[x, y] = screen
    im.save(path)


def _alpha(cut_path, x, y):
    with Image.open(cut_path) as im:
        return im.convert("RGBA").getpixel((x, y))[3]


# 深处边框点（距 bg 与屏幕都 >15px，羽化够不到）。
_BEZEL_PT = (36, 220)
# 屏幕中心点。
_SCREEN_PT = (120, 220)


def test_transparent_screen_frame(tmp_path):
    """外部透明 + 黑边框 + 透明屏幕：识别屏幕、保留边框。"""
    p = tmp_path / "f.png"
    _frame(p, bg=(0, 0, 0, 0), screen=(0, 0, 0, 0))
    r = detect_screen_rect(p, refresh=True)
    assert r["detected"] is True and r["method"] == "color"
    x, y, w, h = r["screen"]
    assert abs(x - 60) <= 4 and abs(y - 60) <= 4
    cut = p.with_name(r["overlay_file"])
    assert _alpha(cut, *_SCREEN_PT) == 0     # 屏幕透明
    assert _alpha(cut, *_BEZEL_PT) >= 250    # 边框保留(深处不受羽化影响)


def test_solid_gray_bg_and_screen_removed_bezel_kept(tmp_path):
    """灰背景 + 黑边框 + 白屏幕（用户真实场景）：去背景+抠屏幕，只留黑边框。"""
    p = tmp_path / "g.png"
    _frame(p, bg=(246, 246, 246, 255), bezel_rgb=(3, 3, 3), screen=(255, 255, 255, 255))
    r = detect_screen_rect(p, refresh=True)
    assert r["detected"] is True and r["method"] == "color"
    assert r["bg_removed"] is True
    cut = p.with_name(r["overlay_file"])
    assert _alpha(cut, 2, 2) == 0            # 背景去掉
    assert _alpha(cut, *_SCREEN_PT) == 0     # 屏幕去掉
    assert _alpha(cut, *_BEZEL_PT) >= 250    # 黑边框保留


def test_same_color_bg_and_screen_separated_by_bezel(tmp_path):
    """背景与屏幕同色，仅靠黑边框隔开：仍应分别去掉、保留边框。"""
    p = tmp_path / "same.png"
    _frame(p, bg=(246, 246, 246, 255), bezel_rgb=(3, 3, 3), screen=(246, 246, 246, 255))
    r = detect_screen_rect(p, refresh=True)
    assert r["method"] == "color" and r["bg_removed"] is True
    cut = p.with_name(r["overlay_file"])
    assert _alpha(cut, 2, 2) == 0
    assert _alpha(cut, *_SCREEN_PT) == 0
    assert _alpha(cut, *_BEZEL_PT) >= 250


def test_no_gray_fringe_after_bg_removal(tmp_path):
    """去背景后边框外侧不应残留"不透明的浅灰毛边"（毛边问题回归测试）。"""
    import numpy as np
    from PIL import Image as _I, ImageFilter as _F
    p = tmp_path / "fringe.png"
    # 灰背景 + 黑边框 + 白屏幕，边框边缘带一圈抗锯齿(模拟真实).
    _frame(p, bg=(246, 246, 246, 255), bezel_rgb=(8, 8, 8), screen=(250, 250, 250, 255))
    r = detect_screen_rect(p, refresh=True)
    a = np.array(_I.open(p.with_name(r["overlay_file"])).convert("RGBA")).astype(int)
    alpha, rgb = a[..., 3], a[..., 0]
    transp = alpha <= 40
    td = np.array(_I.fromarray((transp.astype(np.uint8) * 255), "L").filter(_F.MaxFilter(5))) > 127
    halo = (alpha > 60) & (rgb > 90) & td   # 边界处仍不透明且偏亮 = 灰毛边
    assert int(halo.sum()) == 0


def test_full_opaque_no_bezel_falls_back(tmp_path):
    """整图单色、无边框：去背景会抹掉一切 → 放弃去背景，屏幕走兜底。"""
    p = tmp_path / "flat.png"
    Image.new("RGBA", (120, 240), (10, 20, 30, 255)).save(p)
    r = detect_screen_rect(p, refresh=True)
    assert r["detected"] is False and r["method"] == "fallback"
    assert r["bg_removed"] is False


def test_sidecar_cached(tmp_path):
    p = tmp_path / "c.png"
    _frame(p, bg=(246, 246, 246, 255), bezel_rgb=(3, 3, 3))
    detect_screen_rect(p, refresh=True)
    sidecar = p.with_suffix(p.suffix + ".rect.json")
    assert sidecar.exists()
    assert detect_screen_rect(p)["screen"] == detect_screen_rect(p)["screen"]
