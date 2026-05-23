"""Copy Gen 生成主入口。

quick generate（无 Agent）与 agent generate（含 Agent system prompt）共用同一
段 prompt 构造逻辑。Phase-1：N 个版本顺序调 LLM（time.perf_counter() 计时），
解析每个响应为 VoiceConfig 列表，写一条 CopyGenHistory 历史。
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...config import Settings
from ...models.copy_gen import CopyGenAgent, CopyGenHistory
from ...schemas.copy_gen import GenerateRequest, GenerateResponse, VersionOut, VoiceLineOut
from . import agent_service, model_config_service
from .llm_client import ResolvedModelConfig, build_messages, chat_completion
from .templates import get_platform_tone, get_template
from .voice_config import (
    join_plain_text,
    join_qwen3_tts_text,
    parse_lines,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt 组装（移植自 bzyagent generator.generate_prompt 的核心）
# ─────────────────────────────────────────────────────────────────────────────

def build_user_prompt(
    *,
    topic: str,
    platform: str,
    template_id: str,
    target_words: int,
    tolerance: int,
    script_type: str,
    extra_instructions: Optional[str] = None,
) -> str:
    """生成 LLM 的 user-side prompt。

    - 强约束字数（最高优先级）
    - 携带模板结构提示
    - 携带平台 tone（句长 / 语速 / emoji 偏好）
    - 输出格式：每行 `内容|instruct`，由前端 + voice_config.parse_lines 解析
    """
    target_words = max(10, int(target_words))
    tolerance = max(0, int(tolerance))
    min_words = max(1, target_words - tolerance)
    max_words = target_words + tolerance

    tmpl = get_template(template_id) or {}
    tmpl_name = tmpl.get("name") or template_id
    tmpl_structure = tmpl.get("structure") or []
    tone = get_platform_tone(platform)

    head_blocks: List[str] = []
    head_blocks.append(
        "⚠️ 字数硬性要求（最高优先级，违反即不合格）：\n"
        f"文案总字数必须在 {min_words} 字到 {max_words} 字之间"
        f"（目标 {target_words} 字，上下浮动不超过 {tolerance} 字）。"
        "输出前请自行数字数，不满足则重写。"
    )

    if script_type == "ab_role":
        head_blocks.append(
            f"写《{topic}》的 AB 角色对话口播文案。"
            "只输出对话台词本身，不要输出产品分析、场景分类、功能列表等任何非口播内容。"
        )
    else:
        head_blocks.append(
            f"写《{topic}》的单人口播文案。"
            "只输出口播台词本身，不要输出产品分析、场景分类、功能列表等任何非口播内容。"
        )

    # 模板结构提示
    if tmpl_structure:
        bullets = "\n".join(f"- {s}" for s in tmpl_structure)
        head_blocks.append(
            f"【模板】{tmpl_name}\n请按下面结构展开（顺序、节奏可微调，整体保持模板气质）：\n{bullets}"
        )

    # 平台 tone
    head_blocks.append(
        "【平台调性】\n"
        f"- 平台：{platform}\n"
        f"- 调性：{tone.get('tone', '')}\n"
        f"- 句长：{tone.get('sentence_length', '')}\n"
        f"- 语速：{tone.get('speed', '')}\n"
        f"- emoji 使用：{tone.get('emoji_usage', '')}"
    )

    if script_type == "ab_role":
        output_block = (
            "【输出格式 - AB 角色对话】\n"
            "两个人对话互动，每行格式：角色标识+文案段落内容|Qwen3TTS instruct 指令\n\n"
            "示例：\n"
            "A: 你有没有遇到过这种情况？衣服扣子掉了，找半天找不到同款|"
            "用疑问的语气，引发共鸣，语速适中\n"
            "B: 太有了！我之前为这个事烦透了，直到我发现了这款万能扣！|"
            "用兴奋的语气，表达同感，语速稍快\n"
        )
    else:
        output_block = (
            "【输出格式】\n"
            "按情绪变化自然分段，每行格式：文案段落内容|Qwen3TTS instruct 指令\n\n"
            "Qwen3TTS 官方 instruct 示例：\n"
            "- 用特别愤怒的语气说\n"
            "- 语速较快，带有明显的上扬语调，适合介绍时尚产品\n\n"
            "示例：\n"
            "这都2026年了，不会还有人在花钱听歌吧|"
            "用惊讶夸张的语气开场，制造悬念感，语速稍快，音调偏高\n"
            "汽水音乐直接开启免费听歌加轻松赚双buff|"
            "用兴奋惊喜的语气，像发现宝藏一样分享，语速加快，有感染力\n"
        )

    instruct_rules = (
        "instruct 编写：包含语气/情绪 + 语速 + 音调/氛围，一句完整自然语言。\n"
        f"⚠️ 再次强调：总字数必须 ≥ {min_words} 字且 ≤ {max_words} 字。"
        "输出前请确认字数达标。只写内容，不要其他东西。"
    )

    blocks = head_blocks + [output_block, instruct_rules]
    if extra_instructions and extra_instructions.strip():
        blocks.append(f"【额外指令】\n{extra_instructions.strip()}")
    return "\n\n".join(blocks)


# ─────────────────────────────────────────────────────────────────────────────
# 模型解析（model_config_id / inline / 默认）
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_model_for_request(
    db: Session,
    payload: GenerateRequest,
    settings: Settings,
    agent: Optional[CopyGenAgent] = None,
) -> Tuple[ResolvedModelConfig, Optional[int]]:
    """返回 (ResolvedModelConfig, db_model_config_id_or_None)。

    优先级：
    1. payload.model_config_inline 显式覆盖
    2. payload.model_config_id 指定保存好的 ModelConfig
    3. Agent.model_config_id
    4. 报错（前端必须二选一）
    """
    if payload.model_config_inline:
        return (
            model_config_service.resolve_inline(payload.model_config_inline, settings),
            None,
        )

    cid = payload.model_config_id or (agent.model_config_id if agent else None)
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="缺少模型配置：请提供 model_config_id 或 model_config_inline，"
            "或在 Agent 上预先绑定一个 ModelConfig。",
        )

    obj = model_config_service.get_config(db, int(cid))
    if not obj:
        raise HTTPException(status_code=404, detail=f"ModelConfig id={cid} 不存在")
    resolved = model_config_service.resolve(obj, settings)
    if not resolved.api_key:
        raise HTTPException(
            status_code=400,
            detail=f"ModelConfig id={cid} 的 api_key 解密失败或为空，请重新保存",
        )
    return resolved, obj.id


# ─────────────────────────────────────────────────────────────────────────────
# 核心生成（共用 quick / agent）
# ─────────────────────────────────────────────────────────────────────────────

def _run_generation(
    *,
    db: Session,
    settings: Settings,
    payload: GenerateRequest,
    agent: Optional[CopyGenAgent],
) -> GenerateResponse:
    model_cfg, model_cfg_id = _resolve_model_for_request(db, payload, settings, agent)

    agent_system_prompt: Optional[str] = None
    if agent is not None:
        agent_system_prompt = agent_service.build_system_prompt(
            db, agent, extra_instructions=None
        )

    user_prompt = build_user_prompt(
        topic=payload.topic,
        platform=payload.platform,
        template_id=payload.template,
        target_words=payload.target_words,
        tolerance=payload.tolerance,
        script_type=payload.script_type,
        extra_instructions=payload.extra_instructions,
    )
    logger.info(
        "[copy_gen] request topic=%r platform=%s template=%s script_type=%s "
        "target=%d±%d versions=%d agent_id=%s model_config_id=%s model=%s",
        payload.topic,
        payload.platform,
        payload.template,
        payload.script_type,
        payload.target_words,
        payload.tolerance,
        payload.num_versions,
        agent.id if agent else None,
        model_cfg_id,
        model_cfg.model_name,
    )
    logger.info("[copy_gen] user_prompt=%s", user_prompt)
    if agent_system_prompt:
        logger.info("[copy_gen] agent_system_prompt=%s", agent_system_prompt)
    if model_cfg.system_prompt:
        logger.info("[copy_gen] model_system_prompt=%s", model_cfg.system_prompt)

    versions: List[VersionOut] = []
    t_total = time.perf_counter()
    for i in range(payload.num_versions):
        messages = build_messages(
            user_prompt,
            system_prompt=model_cfg.system_prompt,
            agent_system_prompt=agent_system_prompt,
        )
        t0 = time.perf_counter()
        logger.info(
            "[copy_gen] generate version %d/%d topic=%s model=%s",
            i + 1,
            payload.num_versions,
            payload.topic,
            model_cfg.model_name,
        )
        try:
            content = chat_completion(
                model_cfg,
                messages,
                timeout=settings.copy_gen_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[copy_gen] LLM 调用失败 v%d", i + 1)
            raise HTTPException(status_code=502, detail=f"LLM 调用失败：{exc}")

        elapsed_v = time.perf_counter() - t0
        logger.info(
            "[copy_gen] version %d done in %.2fs raw_len=%d",
            i + 1,
            elapsed_v,
            len(content or ""),
        )

        cfgs = parse_lines(content)
        plain = join_plain_text(cfgs) or content.strip()
        qwen3 = join_qwen3_tts_text(cfgs) or content.strip()

        voice_lines = [
            VoiceLineOut(**c.to_dict()) for c in cfgs
        ]
        versions.append(
            VersionOut(
                index=i + 1,
                content=plain,
                qwen3_tts_text=qwen3,
                voice_lines=voice_lines,
                word_count=len(plain),
            )
        )
        logger.info(
            "[copy_gen] version %d parsed lines=%d plain_chars=%d qwen3_chars=%d",
            i + 1,
            len(voice_lines),
            len(plain),
            len(qwen3),
        )

    elapsed_total = time.perf_counter() - t_total

    # 持久化历史
    history_payload: Dict[str, Any] = payload.model_dump()
    # 不要把 inline api_key 落库
    if history_payload.get("model_config_inline"):
        inline = dict(history_payload["model_config_inline"])
        inline["api_key"] = "***"
        history_payload["model_config_inline"] = inline

    results_dict: Dict[str, Any] = {
        "model_used": model_cfg.model_name,
        "elapsed_sec": round(elapsed_total, 3),
        "versions": [v.model_dump() for v in versions],
    }

    history = CopyGenHistory(
        agent_id=agent.id if agent else None,
        model_config_id=model_cfg_id,
        payload_json=json.dumps(history_payload, ensure_ascii=False),
        results_json=json.dumps(results_dict, ensure_ascii=False),
        user_id=None,  # Phase-1：未关联当前登录用户
        created_at=datetime.utcnow(),
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    logger.info(
        "[copy_gen] generation_id=%d total_elapsed=%.2fs versions=%d",
        history.id,
        elapsed_total,
        len(versions),
    )

    return GenerateResponse(
        generation_id=history.id,
        model_used=model_cfg.model_name,
        elapsed_sec=round(elapsed_total, 3),
        versions=versions,
        prompt_used=user_prompt,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

def generate(
    payload: GenerateRequest, db: Session, settings: Settings
) -> GenerateResponse:
    """快速生成（无 Agent）。"""
    return _run_generation(db=db, settings=settings, payload=payload, agent=None)


def generate_with_agent(
    agent_id: int,
    payload: GenerateRequest,
    db: Session,
    settings: Settings,
) -> GenerateResponse:
    """使用指定 Agent 生成（含 Agent system prompt）。"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")

    # 用 Agent 默认值补全 payload（前端没传则回退到 Agent default）
    data = payload.model_dump(exclude_unset=True)
    if "platform" not in data and agent.platform:
        payload = payload.model_copy(update={"platform": agent.platform})
    if "template" not in data and agent.default_template:
        payload = payload.model_copy(update={"template": agent.default_template})
    if "target_words" not in data:
        payload = payload.model_copy(update={"target_words": agent.default_target_words})
    if "tolerance" not in data:
        payload = payload.model_copy(update={"tolerance": agent.default_tolerance})
    if "script_type" not in data and agent.default_script_type:
        payload = payload.model_copy(update={"script_type": agent.default_script_type})

    return _run_generation(db=db, settings=settings, payload=payload, agent=agent)


# ─────────────────────────────────────────────────────────────────────────────
# 历史
# ─────────────────────────────────────────────────────────────────────────────

def list_history(
    db: Session, *, limit: int = 20, offset: int = 0
) -> Tuple[List[CopyGenHistory], int]:
    q = db.query(CopyGenHistory).order_by(CopyGenHistory.created_at.desc())
    total = q.count()
    items = list(q.offset(offset).limit(limit).all())
    return items, total


def delete_history(db: Session, history_id: int) -> bool:
    obj = (
        db.query(CopyGenHistory).filter(CopyGenHistory.id == history_id).first()
    )
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def history_to_dict(h: CopyGenHistory) -> Dict[str, Any]:
    try:
        payload = json.loads(h.payload_json) if h.payload_json else {}
    except Exception:
        payload = {}
    try:
        results = json.loads(h.results_json) if h.results_json else {}
    except Exception:
        results = {}
    return {
        "id": h.id,
        "agent_id": h.agent_id,
        "model_config_id": h.model_config_id,
        "payload": payload,
        "results": results,
        "created_at": h.created_at,
    }
