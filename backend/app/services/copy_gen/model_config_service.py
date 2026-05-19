"""CopyGenModelConfig CRUD + Fernet 加解密 + 连通性测试。

加密 Key 解析顺序：
1. `settings.copy_gen_llm_key`（环境变量 `COPY_GEN_LLM_KEY`）
2. `data/.copy_gen_key` 文件（首次启动时自动创建并持久化）

Fernet 是对称加密，丢失 key 等同于 DB 中已加密的 api_key 全部不可读，因此
在自动生成 key 时会同步打 INFO 日志提示用户备份。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from ...config import Settings
from ...models.copy_gen import CopyGenModelConfig
from ...schemas.copy_gen import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelTestResponse,
)
from .llm_client import ResolvedModelConfig, build_messages, chat_completion

logger = logging.getLogger(__name__)


_KEY_LOCK = threading.Lock()
_FERNET_CACHE: dict = {}  # {"key": bytes, "fernet": Fernet}


def _resolve_fernet(settings: Settings):
    """惰性构造 Fernet 实例（线程安全）。"""
    from cryptography.fernet import Fernet  # local import → avoid hard dep on import-time

    with _KEY_LOCK:
        if _FERNET_CACHE.get("fernet") is not None:
            return _FERNET_CACHE["fernet"]

        # 1) env / settings
        key_str = (settings.copy_gen_llm_key or "").strip()
        key_bytes: Optional[bytes] = None
        if key_str:
            try:
                # 试图把环境变量的字符串解释为 Fernet key（urlsafe base64 32 字节）
                key_bytes = key_str.encode("utf-8")
                Fernet(key_bytes)  # validate
            except Exception:
                logger.warning(
                    "[copy_gen] COPY_GEN_LLM_KEY 不是合法 Fernet key，将回落到 data/.copy_gen_key"
                )
                key_bytes = None

        # 2) data/.copy_gen_key 文件
        if key_bytes is None:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            key_file = settings.data_dir / ".copy_gen_key"
            if key_file.exists():
                try:
                    key_bytes = key_file.read_bytes().strip()
                    Fernet(key_bytes)  # validate
                except Exception:
                    logger.warning(
                        "[copy_gen] data/.copy_gen_key 内容损坏，将重新生成（旧密文将不可读）"
                    )
                    key_bytes = None

            # 3) 自动生成 + 持久化
            if key_bytes is None:
                key_bytes = Fernet.generate_key()
                try:
                    key_file.write_bytes(key_bytes)
                    logger.info(
                        "[copy_gen] 已自动生成 Fernet key 并写入 %s — 请妥善备份",
                        key_file,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[copy_gen] 无法写入 .copy_gen_key：%s", exc)

        fernet = Fernet(key_bytes)
        _FERNET_CACHE["key"] = key_bytes
        _FERNET_CACHE["fernet"] = fernet
        return fernet


def encrypt(plain: str, settings: Settings) -> bytes:
    if not plain:
        return b""
    fernet = _resolve_fernet(settings)
    return fernet.encrypt(plain.encode("utf-8"))


def decrypt(enc: Optional[bytes], settings: Settings) -> str:
    if not enc:
        return ""
    fernet = _resolve_fernet(settings)
    try:
        return fernet.decrypt(enc).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[copy_gen] api_key 解密失败：%s", exc)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

def list_configs(db: Session) -> List[CopyGenModelConfig]:
    return list(db.query(CopyGenModelConfig).order_by(CopyGenModelConfig.id.asc()).all())


def get_config(db: Session, config_id: int) -> Optional[CopyGenModelConfig]:
    return db.query(CopyGenModelConfig).filter(CopyGenModelConfig.id == config_id).first()


def create_config(
    db: Session, payload: ModelConfigCreate, settings: Settings
) -> CopyGenModelConfig:
    obj = CopyGenModelConfig(
        name=payload.name,
        model_name=payload.model_name,
        base_url=(payload.base_url or settings.copy_gen_default_base_url or "").strip(),
        api_key_enc=encrypt(payload.api_key, settings),
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        system_prompt=payload.system_prompt,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_config(
    db: Session,
    config_id: int,
    payload: ModelConfigUpdate,
    settings: Settings,
) -> Optional[CopyGenModelConfig]:
    obj = get_config(db, config_id)
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data:
        new_key = data.pop("api_key")
        # 显式传空字符串 → 视为「不变」；显式传 None 同义；
        # 用户必须主动给非空字符串才会被替换
        if new_key:
            obj.api_key_enc = encrypt(new_key, settings)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_config(db: Session, config_id: int) -> bool:
    obj = get_config(db, config_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 序列化（→ Pydantic ModelConfigOut.has_api_key）
# ─────────────────────────────────────────────────────────────────────────────

def to_out_dict(obj: CopyGenModelConfig) -> dict:
    return {
        "id": obj.id,
        "name": obj.name,
        "model_name": obj.model_name,
        "base_url": obj.base_url,
        "has_api_key": bool(obj.api_key_enc),
        "temperature": obj.temperature,
        "max_tokens": obj.max_tokens,
        "system_prompt": obj.system_prompt,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 解密 → ResolvedModelConfig
# ─────────────────────────────────────────────────────────────────────────────

def resolve(
    obj: CopyGenModelConfig, settings: Settings
) -> ResolvedModelConfig:
    return ResolvedModelConfig(
        name=obj.name,
        model_name=obj.model_name,
        base_url=obj.base_url or settings.copy_gen_default_base_url,
        api_key=decrypt(obj.api_key_enc, settings),
        temperature=obj.temperature,
        max_tokens=obj.max_tokens,
        system_prompt=obj.system_prompt,
    )


def resolve_inline(
    payload: ModelConfigCreate, settings: Settings
) -> ResolvedModelConfig:
    """对 inline ModelConfig（生成请求里携带的临时配置）做一次解析。"""
    return ResolvedModelConfig(
        name=payload.name or "(inline)",
        model_name=payload.model_name,
        base_url=(payload.base_url or settings.copy_gen_default_base_url or "").strip(),
        api_key=payload.api_key,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        system_prompt=payload.system_prompt,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 连通性测试
# ─────────────────────────────────────────────────────────────────────────────

def _friendly_llm_error(exc: Exception) -> str:
    """把底层 SDK 的英文异常翻译成对前端用户更友好的中文提示。

    保留 `type(exc).__name__` 与原始 message，便于排查；仅在能识别成已知模式时
    在最前面加一段「人话」前缀和行动建议。
    """
    raw = f"{type(exc).__name__}: {exc}"
    text = str(exc).lower()

    if "credit balance" in text or "insufficient" in text or "quota" in text or "billing" in text:
        return (
            "账户余额不足或额度耗尽 — 请到模型供应商控制台充值/续费后重试。"
            f"\n原始错误：{raw}"
        )
    if "authentication" in text or "invalid api key" in text or "incorrect api key" in text \
            or "401" in text or "unauthorized" in text:
        return (
            "API Key 鉴权失败 — 请检查 base_url 与 api_key 是否匹配该供应商。"
            f"\n原始错误：{raw}"
        )
    if "model" in text and ("not found" in text or "does not exist" in text or "404" in text):
        return (
            f"模型名称未被服务端识别 — 请确认 `{getattr(exc, 'model', '')}` 是否为当前 "
            "base_url 下可用的模型 ID（注意 Anthropic 当前可用：claude-opus-4-7 / "
            "claude-sonnet-4-6 / claude-haiku-4-5-20251001）。"
            f"\n原始错误：{raw}"
        )
    if "rate_limit" in text or "429" in text or "too many requests" in text:
        return f"被服务端限流（rate limit），请稍后再试。\n原始错误：{raw}"
    if "timeout" in text or "timed out" in text:
        return f"请求超时 — 网络不通或服务端响应过慢。\n原始错误：{raw}"
    if "connection" in text and ("refused" in text or "reset" in text or "aborted" in text):
        return f"网络连接异常 — 请检查 base_url 是否可达 / 代理设置。\n原始错误：{raw}"
    return raw


def test_connectivity(
    model_config: ResolvedModelConfig, settings: Settings
) -> ModelTestResponse:
    """最小化 chat.completions.create ping。返回耗时（ms）与可读 message。"""
    messages = build_messages("ping", system_prompt=None, agent_system_prompt=None)
    t0 = time.perf_counter()
    try:
        # 故意把 max_tokens 限制得很低，节省 token / 时间
        reply = chat_completion(
            model_config,
            messages,
            timeout=min(settings.copy_gen_timeout, 30),
            temperature=0.0,
            max_tokens=8,
        )
        latency = int((time.perf_counter() - t0) * 1000)
        snippet = (reply or "")[:80]
        return ModelTestResponse(
            ok=True,
            message=f"OK — reply: {snippet}",
            latency_ms=latency,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - t0) * 1000)
        return ModelTestResponse(
            ok=False, message=_friendly_llm_error(exc), latency_ms=latency
        )
