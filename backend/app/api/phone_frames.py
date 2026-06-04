"""手机边框 PNG 的轻量上传 / 列表 / 取文件接口（不建数据库表，直接落盘）。

存储：data/uploads/phone_frames/{filename}，同名 .rect.json sidecar 缓存屏幕区。
仅接受带透明通道的图片（.png / .webp）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import Settings
from ..dependencies import get_app_settings
from ..utils.phone_frame_utils import detect_screen_rect

router = APIRouter(prefix="/api/phone-frames", tags=["phone-frames"])

_ALLOWED_SUFFIXES = {".png", ".webp"}


def _frames_dir(settings: Settings) -> Path:
    d = settings.data_dir / "uploads" / "phone_frames"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(filename: str) -> str:
    """只取文件名部分，防目录穿越。"""
    name = Path(filename or "").name.strip()
    if not name or name.startswith("."):
        raise HTTPException(status_code=400, detail="文件名非法")
    if Path(name).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="手机边框仅支持 PNG / WebP（需透明屏幕区）")
    return name


def _frame_info(settings: Settings, path: Path) -> dict:
    rect = detect_screen_rect(path)
    return {
        "name": path.name,
        "url": f"/api/phone-frames/{path.name}/file",
        "frame_w": rect.get("frame_w"),
        "frame_h": rect.get("frame_h"),
        "screen": rect.get("screen"),
        "detected": rect.get("detected", False),
        "method": rect.get("method", "fallback"),
        "size": int(path.stat().st_size),
    }


@router.post("", response_model=dict)
async def upload_phone_frame(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_app_settings),
):
    name = _safe_name(file.filename or "")
    frames_dir = _frames_dir(settings)
    dst = frames_dir / name
    with dst.open("wb") as out:
        out.write(await file.read())
    # 重新识别屏幕区（覆盖旧 sidecar）。
    detect_screen_rect(dst, refresh=True)
    return _frame_info(settings, dst)


@router.get("", response_model=list[dict])
async def list_phone_frames(settings: Settings = Depends(get_app_settings)):
    frames_dir = _frames_dir(settings)
    frames = [
        p
        for p in sorted(frames_dir.iterdir())
        if p.is_file()
        and p.suffix.lower() in _ALLOWED_SUFFIXES
        and not p.name.endswith(".cut.png")  # 排除自动抠洞生成的派生图
    ]
    return [_frame_info(settings, p) for p in frames]


@router.get("/{name}/file")
async def get_phone_frame_file(name: str, settings: Settings = Depends(get_app_settings)):
    safe = Path(name).name
    path = _frames_dir(settings) / safe
    if not path.exists() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=404, detail="手机边框不存在")
    media = "image/webp" if path.suffix.lower() == ".webp" else "image/png"
    return FileResponse(str(path), media_type=media)


@router.delete("/{name}", response_model=dict)
async def delete_phone_frame(name: str, settings: Settings = Depends(get_app_settings)):
    safe = Path(name).name
    frames_dir = _frames_dir(settings)
    path = frames_dir / safe
    if not path.exists() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=404, detail="手机边框不存在")
    # 连同派生的抠洞图与 sidecar 一并删除。
    path.unlink(missing_ok=True)
    (frames_dir / (path.stem + ".cut.png")).unlink(missing_ok=True)
    path.with_suffix(path.suffix + ".rect.json").unlink(missing_ok=True)
    return {"message": "已删除", "name": safe}
