"""日志查看器 API。

GET  /api/logs/categories                   — 4 类别 + 各自 item 数量与总字节
GET  /api/logs/{category}/items             — 该类别下所有 item（按 mtime 倒序）
GET  /api/logs/{category}/{item_id}/tail    — tail 末尾 N 行（默认 1000）
GET  /api/logs/{category}/{item_id}/download — 下载完整内容
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..config import Settings
from ..dependencies import get_app_settings
from ..services.log_viewer_service import (
    list_categories,
    list_items,
    read_full,
    tail_log,
)


router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/categories")
async def api_log_categories(settings: Settings = Depends(get_app_settings)):
    return list_categories(settings.data_dir)


@router.get("/{category}/items")
async def api_log_items(
    category: str,
    settings: Settings = Depends(get_app_settings),
):
    try:
        return list_items(settings.data_dir, category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{category}/{item_id}/tail")
async def api_log_tail(
    category: str,
    item_id: str,
    lines: int = Query(1000, ge=1, le=100_000),
    settings: Settings = Depends(get_app_settings),
):
    try:
        return tail_log(settings.data_dir, category, item_id, lines)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{category}/{item_id}/download")
async def api_log_download(
    category: str,
    item_id: str,
    settings: Settings = Depends(get_app_settings),
):
    try:
        content, filename = read_full(settings.data_dir, category, item_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ASCII-safe Content-Disposition (RFC 5987 fallback for non-ASCII)
    safe_ascii = "".join(ch if ord(ch) < 128 else "_" for ch in filename)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_ascii}"; '
                f"filename*=UTF-8''{filename}"
            ),
        },
    )
