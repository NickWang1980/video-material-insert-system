from __future__ import annotations

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..models.database import SessionLocal
from ..models.audit_log import AuditLog

# (compiled_regex, entity_type, action_label or None)
# action_label=None → derive from HTTP method
_ROUTES: list[tuple[re.Pattern, str, str | None]] = [
    # source videos
    (re.compile(r"^/api/source-videos/\d+/asr/retry$"), "source_video", "重试ASR识别"),
    (re.compile(r"^/api/source-videos/\d+$"), "source_video", None),
    (re.compile(r"^/api/source-videos$"), "source_video", "上传源视频"),
    # materials
    (re.compile(r"^/api/materials/products/\d+/scripts$"), "material_script_folder", "创建脚本文件夹"),
    (re.compile(r"^/api/materials/products/\d+$"), "material_product", None),
    (re.compile(r"^/api/materials/products$"), "material_product", "创建产品目录"),
    (re.compile(r"^/api/materials/scripts/\d+$"), "material_script_folder", None),
    (re.compile(r"^/api/materials/\d+/file$"), "material", "归档素材"),
    (re.compile(r"^/api/materials/\d+/folders/\d+$"), "material", "取消归档素材"),
    (re.compile(r"^/api/materials/\d+$"), "material", None),
    (re.compile(r"^/api/materials$"), "material", "上传素材"),
    # tasks
    (re.compile(r"^/api/tasks/keyword-collision-check$"), "task", "关键词碰撞检测"),
    (re.compile(r"^/api/tasks/resume-all$"), "task", "批量恢复任务"),
    (re.compile(r"^/api/tasks/\d+/retry$"), "task", "重试任务"),
    (re.compile(r"^/api/tasks/\d+/stop$"), "task", "停止任务"),
    (re.compile(r"^/api/tasks/\d+$"), "task", None),
    (re.compile(r"^/api/tasks$"), "task", "创建任务"),
    # config templates
    (re.compile(r"^/api/config-templates/import$"), "config_template", "导入配置模板"),
    (re.compile(r"^/api/config-templates/\d+$"), "config_template", None),
    (re.compile(r"^/api/config-templates$"), "config_template", "创建配置模板"),
    # rough cut
    (re.compile(r"^/api/rough-cut/ffmpeg/clear$"), "rough_cut_ffmpeg", "清除FFmpeg进程"),
    (re.compile(r"^/api/rough-cut/projects/\d+/assets/\d+/manual-gate$"), "rough_cut_asset", "更新素材审核"),
    (re.compile(r"^/api/rough-cut/projects/\d+/assets/\d+$"), "rough_cut_asset", None),
    (re.compile(r"^/api/rough-cut/projects/\d+/assets$"), "rough_cut_asset", "上传项目素材"),
    (re.compile(r"^/api/rough-cut/projects/\d+/split-script$"), "rough_cut_project", "分割剧本"),
    (re.compile(r"^/api/rough-cut/projects/\d+/assign-roles$"), "rough_cut_project", "分配角色"),
    (re.compile(r"^/api/rough-cut/projects/\d+/settings$"), "rough_cut_project", "更新项目设置"),
    (re.compile(r"^/api/rough-cut/projects/\d+/build-timeline$"), "rough_cut_project", "构建时间线"),
    (re.compile(r"^/api/rough-cut/projects/\d+/sentences/\d+$"), "rough_cut_sentence", "编辑分镜句子"),
    (re.compile(r"^/api/rough-cut/projects/\d+/regenerate-sentence/\d+$"), "rough_cut_sentence", "重新生成句子"),
    (re.compile(r"^/api/rough-cut/projects/\d+/export$"), "rough_cut_project", "导出项目"),
    (re.compile(r"^/api/rough-cut/projects/\d+/stop$"), "rough_cut_project", "停止项目处理"),
    (re.compile(r"^/api/rough-cut/projects/\d+/sentence-preview/\d+$"), "rough_cut_sentence", "生成句子预览"),
    (re.compile(r"^/api/rough-cut/projects/\d+$"), "rough_cut_project", None),
    (re.compile(r"^/api/rough-cut/projects$"), "rough_cut_project", "创建混剪项目"),
    # settings
    (re.compile(r"^/api/settings$"), "settings", "更新全局设置"),
]

_METHOD_VERB: dict[str, str] = {
    "POST": "创建",
    "PUT": "更新",
    "PATCH": "修改",
    "DELETE": "删除",
}

_ENTITY_LABEL: dict[str, str] = {
    "source_video": "源视频",
    "material": "素材",
    "material_product": "产品目录",
    "material_script_folder": "脚本文件夹",
    "task": "任务",
    "config_template": "配置模板",
    "rough_cut_project": "混剪项目",
    "rough_cut_asset": "混剪素材",
    "rough_cut_sentence": "分镜句子",
    "rough_cut_ffmpeg": "FFmpeg进程",
    "settings": "系统设置",
}


def _resolve(path: str, method: str) -> tuple[str | None, str]:
    for pattern, entity_type, label in _ROUTES:
        if pattern.match(path):
            if label is None:
                verb = _METHOD_VERB.get(method, method)
                label = f"{verb}{_ENTITY_LABEL.get(entity_type, entity_type)}"
            return entity_type, label
    return None, f"{method} {path}"


def _entity_id(path: str) -> str | None:
    ids = re.findall(r"/(\d+)", path)
    return ids[-1] if ids else None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - t0) * 1000)

        path = request.url.path
        entity_type, action = _resolve(path, request.method)

        db = SessionLocal()
        try:
            db.add(AuditLog(
                method=request.method,
                path=path,
                action=action,
                entity_type=entity_type,
                entity_id=_entity_id(path),
                status_code=response.status_code,
                ip_address=_client_ip(request),
                user_agent=(request.headers.get("user-agent") or "")[:512],
                operator=(request.headers.get("x-operator") or "")[:100] or None,
                source="user",
                duration_ms=duration_ms,
            ))
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

        return response
