from __future__ import annotations

import pytest

from backend.app.utils.csv_utils import parse_config_csv_bytes


def test_parse_config_csv_bytes_ok():
    content = (
        "关键字,素材文件名,素材类型,提示音,显示时长(秒),入场偏移(秒),九宫格位置,透明度,是否循环,触发规则,素材宽度占比(%)\n"
        "家人们,hello.png,图片,ding.mp3,1.5,-0.2,9,100,0,首次触发,30\n"
    ).encode("utf-8")
    items = parse_config_csv_bytes(content)
    assert items[0]["关键字"] == "家人们"
    assert items[0]["九宫格位置"] == 9
    assert items[0]["提示音"] == "ding.mp3"
    assert items[0]["素材宽度占比(%)"] == 30.0


def test_parse_config_csv_bytes_default_size_ratio():
    content = (
        "关键字,素材文件名,素材类型\n"
        "家人们,hello.png,图片\n"
    ).encode("utf-8")
    items = parse_config_csv_bytes(content)
    assert items[0]["提示音"] == "随机"
    assert items[0]["素材宽度占比(%)"] == 25.0


def test_parse_config_csv_bytes_invalid_size_ratio():
    content = (
        "关键字,素材文件名,素材类型,素材宽度占比(%)\n"
        "家人们,hello.png,图片,90\n"
    ).encode("utf-8")
    with pytest.raises(ValueError):
        parse_config_csv_bytes(content)
