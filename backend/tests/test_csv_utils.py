from __future__ import annotations

import pytest

from backend.app.utils.csv_utils import parse_config_csv_bytes


def test_parse_config_csv_bytes_ok():
    content = (
        "关键字,素材文件名,素材类型,提示音,显示时长(秒),入场偏移(秒),九宫格位置,透明度,是否循环,触发规则,素材宽度占比(%),视频起始秒(秒),视频持续秒(秒)\n"
        "家人们,hello.png,图片,ding.mp3,1.5,-0.2,1,100,0,首次触发,30,2,4\n"
    ).encode("utf-8")
    items = parse_config_csv_bytes(content)
    assert items[0]["关键字"] == "家人们"
    assert items[0]["九宫格位置"] == 1
    assert items[0]["提示音"] == "ding.mp3"
    assert items[0]["素材宽度占比(%)"] == 30.0
    assert items[0]["视频起始秒(秒)"] == 2.0
    assert items[0]["视频持续秒(秒)"] == 4.0


def test_parse_config_csv_bytes_default_for_image_and_video():
    content = (
        "关键字,素材文件名,素材类型\n"
        "图片词,hello.png,图片\n"
        "视频词,hello.mp4,短视频\n"
    ).encode("utf-8")
    items = parse_config_csv_bytes(content)
    assert items[0]["显示时长(秒)"] == 2.0
    assert items[0]["九宫格位置"] == 1
    assert items[0]["素材宽度占比(%)"] == 25.0
    assert items[1]["显示时长(秒)"] is None
    assert items[1]["素材宽度占比(%)"] == 70.0
    assert items[1]["视频起始秒(秒)"] == 0.0
    assert items[1]["视频持续秒(秒)"] is None


def test_parse_config_csv_bytes_invalid_video_size_ratio():
    content = (
        "关键字,素材文件名,素材类型,素材宽度占比(%)\n"
        "视频词,hello.mp4,短视频,90\n"
    ).encode("utf-8")
    with pytest.raises(ValueError):
        parse_config_csv_bytes(content)


def test_parse_config_csv_bytes_invalid_non_video_size_ratio():
    content = (
        "关键字,素材文件名,素材类型,素材宽度占比(%)\n"
        "图片词,hello.png,图片,101\n"
    ).encode("utf-8")
    with pytest.raises(ValueError):
        parse_config_csv_bytes(content)


def test_parse_config_csv_bytes_invalid_video_duration():
    content = (
        "关键字,素材文件名,素材类型,视频持续秒(秒)\n"
        "家人们,hello.mp4,短视频,0\n"
    ).encode("utf-8")
    with pytest.raises(ValueError):
        parse_config_csv_bytes(content)
