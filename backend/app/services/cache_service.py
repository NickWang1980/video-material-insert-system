"""可清理缓存的盘点与清理。

严格区分 "项目数据" vs "缓存/临时"：
  - 项目数据（永远不动）：源视频、素材、角色素材、成品视频、报告、SRT、数据库、ASR 模型主文件
  - 缓存（可一键清）：混剪渲染临时目录、单句预览片段、HF 元数据 .cache、旧版本路径残留、E2E 测试产物
  - 任务日志：单独类别，由用户选择是否清

每个类别给出 path + size + count，前端可见后再决定清理。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger()

# 项目根（从本文件位置反推：services > app > backend > <root>）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class CacheCategory:
    """一个可清理的缓存类别。

    safe=True 表示 100% 可清；safe=False 表示需用户额外确认（如日志）。
    paths 列出实际目录；size_bytes / file_count 是聚合统计。
    """
    key: str
    label: str
    description: str
    safe: bool
    paths: list[str]
    size_bytes: int = 0
    file_count: int = 0


def _dir_size_and_count(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    total = 0
    count = 0
    try:
        for f in path.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
                    count += 1
            except OSError:
                continue
    except Exception:
        pass
    return total, count


def _aggregate(paths: list[Path]) -> tuple[int, int]:
    total_b = 0
    total_c = 0
    for p in paths:
        b, c = _dir_size_and_count(p)
        total_b += b
        total_c += c
    return total_b, total_c


def _gather_paths(data_dir: Path, key: str) -> list[Path]:
    """返回某类别下实际存在或预定义的路径。不存在的路径会被过滤掉。"""
    if key == "rough_cut_temp":
        # 单一目录
        return [data_dir / "outputs" / "rough_cut" / "temp"]

    if key == "sentence_previews":
        return [data_dir / "outputs" / "rough_cut" / "sentence_previews"]

    if key == "hf_metadata":
        # 每个模型目录里的 .cache 子目录
        results = []
        models_root = data_dir / "asr_models"
        if models_root.exists():
            for sub in models_root.iterdir():
                if sub.is_dir():
                    cache_sub = sub / ".cache"
                    if cache_sub.exists():
                        results.append(cache_sub)
        return results

    if key == "legacy_paths":
        # 旧版本路径——统一迁移到 outputs/ 和 uploads/ 后留下的空壳
        candidates = [
            data_dir / "output",       # 注意：单数；现在用 outputs/
            data_dir / "reports",      # 已迁到 outputs/reports
            data_dir / "videos",       # 已迁到 uploads/videos
            data_dir / "subtitles",    # 已迁到 uploads/subtitles
        ]
        return [p for p in candidates if p.exists()]

    if key == "e2e_artifacts":
        return [data_dir / "_e2e"]

    if key == "task_logs":
        return [data_dir / "outputs" / "logs"]

    if key == "nuitka_build":
        # Nuitka 把项目入口编译时，在 <root>/dist/ 下产出
        #   <name>.build/  ← 中间产物（C 源码 + .o + scons 缓存，可达数 GB）
        #   <name>.dist/   ← 最终输出（exe + 依赖），保留不删
        # 只清 .build 子目录
        dist = _PROJECT_ROOT / "dist"
        if not dist.exists():
            return []
        return [p for p in dist.iterdir() if p.is_dir() and p.name.endswith(".build")]

    return []


_CATEGORY_DEFS: list[tuple[str, str, str, bool]] = [
    # (key, label, description, safe)
    (
        "rough_cut_temp",
        "混剪渲染临时目录",
        "渲染时切片的中间产物（concat.txt + 临时分段视频），导出完成后无用",
        True,
    ),
    (
        "sentence_previews",
        "单句预览片段",
        "混剪单元里点'预览'生成的小段视频；不影响任何成品，仅占空间",
        True,
    ),
    (
        "hf_metadata",
        "HuggingFace 元数据缓存",
        "ASR 模型目录内的 .cache 子目录（仅元数据，模型主文件不动）",
        True,
    ),
    (
        "legacy_paths",
        "旧版本目录残留",
        "data/{output, reports, videos, subtitles} —— 早期路径，已迁移到 outputs/ 和 uploads/",
        True,
    ),
    (
        "e2e_artifacts",
        "端到端测试产物",
        "data/_e2e —— 自动化测试运行残留",
        True,
    ),
    (
        "task_logs",
        "任务日志",
        "data/outputs/logs —— 历史任务运行日志（如需排查问题请保留）",
        False,
    ),
    (
        "nuitka_build",
        "Nuitka 打包中间产物",
        "dist/*.build —— Nuitka 编译产生的 C 源码 + .o 目标文件 + scons 缓存。最终输出 dist/*.dist/ 不会被删除",
        True,
    ),
]


def list_cache_categories(data_dir: Path) -> list[CacheCategory]:
    out: list[CacheCategory] = []
    for key, label, desc, safe in _CATEGORY_DEFS:
        paths = _gather_paths(data_dir, key)
        size, count = _aggregate(paths)
        out.append(CacheCategory(
            key=key,
            label=label,
            description=desc,
            safe=safe,
            paths=[str(p) for p in paths],
            size_bytes=size,
            file_count=count,
        ))
    return out


def clear_cache(data_dir: Path, category_keys: list[str]) -> dict:
    """按类别清理。返回 {category_key: {paths: [...], freed_bytes, freed_files, errors: []}}"""
    valid_keys = {key for key, _, _, _ in _CATEGORY_DEFS}
    summary: dict = {}

    for key in category_keys:
        if key not in valid_keys:
            summary[key] = {"error": "未知类别", "freed_bytes": 0, "freed_files": 0, "paths": []}
            continue

        paths = _gather_paths(data_dir, key)
        before_bytes, before_count = _aggregate(paths)
        deleted_paths: list[str] = []
        errors: list[str] = []

        for p in paths:
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=False)
                elif p.is_file():
                    p.unlink()
                deleted_paths.append(str(p))
            except Exception as e:
                logger.exception(f"clear_cache failed: {p}")
                # 二次软删除尝试，确保最大限度释放空间
                try:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    elif p.is_file():
                        p.unlink(missing_ok=True)
                except Exception:
                    pass
                if p.exists():
                    errors.append(f"{p}: {e}"[:200])
                else:
                    deleted_paths.append(str(p))

        # 重建顶层目录（保持系统其它代码用得上的路径存在）
        if key == "rough_cut_temp":
            (data_dir / "outputs" / "rough_cut" / "temp").mkdir(parents=True, exist_ok=True)
        elif key == "sentence_previews":
            (data_dir / "outputs" / "rough_cut" / "sentence_previews").mkdir(parents=True, exist_ok=True)
        elif key == "task_logs":
            (data_dir / "outputs" / "logs").mkdir(parents=True, exist_ok=True)

        summary[key] = {
            "freed_bytes": before_bytes,
            "freed_files": before_count,
            "paths": deleted_paths,
            "errors": errors,
        }
        logger.info(
            f"clear_cache {key}: freed {before_bytes // (1024*1024)} MB / {before_count} files"
        )

    return summary
