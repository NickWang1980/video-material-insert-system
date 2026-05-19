"""OpenAI 兼容 LLM 客户端封装。

Phase-1 选择最小化：
- 仅暴露 `chat_completion(model_config, messages, ...)`
- 使用官方 `openai>=1.0.0` SDK 的 `OpenAI(base_url=..., api_key=...)`，因此
  OpenAI / Qwen / Anthropic（兼容接口）/ 本地 vLLM 均可通过 base_url 切换
- timeout 来自 `settings.copy_gen_timeout`，并允许调用方 override
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 工具：把 messages/response 安全地序列化进日志 ──────────────────────────
# 为避免 api_key 通过 base_url path、header 等意外途径进入日志，这里只输出
# messages / response 的可读字段；任何 base_url / api_key 都不会写入。

_MAX_LOG_FIELD = 100_000  # 单字段截断阈值，防止单个 prompt/response 把日志撑爆


def _safe_dump(value: Any) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        s = repr(value)
    if len(s) > _MAX_LOG_FIELD:
        s = s[:_MAX_LOG_FIELD] + f"... (truncated, total {len(s)} chars)"
    return s


def _serialize_response(response: Any) -> Dict[str, Any]:
    """Pull useful debug info out of an OpenAI ChatCompletion object."""
    out: Dict[str, Any] = {}
    try:
        out["id"] = getattr(response, "id", None)
        out["model"] = getattr(response, "model", None)
        out["created"] = getattr(response, "created", None)
        out["object"] = getattr(response, "object", None)
        # choices
        choices = getattr(response, "choices", []) or []
        out["choices"] = []
        for ch in choices:
            msg = getattr(ch, "message", None)
            out["choices"].append({
                "index": getattr(ch, "index", None),
                "finish_reason": getattr(ch, "finish_reason", None),
                "role": getattr(msg, "role", None) if msg else None,
                "content": getattr(msg, "content", None) if msg else None,
            })
        # usage
        usage = getattr(response, "usage", None)
        if usage is not None:
            out["usage"] = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
    except Exception as exc:  # noqa: BLE001
        out["_serialize_error"] = str(exc)
    return out


@dataclass
class ResolvedModelConfig:
    """运行时已解密、可直接传给 OpenAI() 的模型配置快照。

    与 ORM `CopyGenModelConfig` 解耦，便于 inline 模型配置场景使用。
    """

    name: str
    model_name: str
    base_url: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None


def _build_client(base_url: str, api_key: str, timeout: int):
    """惰性导入 openai SDK，避免在没有依赖时 import 时就崩。"""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "openai SDK 未安装；请在 backend/requirements.txt 中加入 openai>=1.0.0,<2.0"
        ) from exc

    kwargs: Dict[str, Any] = {"api_key": api_key, "timeout": timeout}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _is_anthropic_target(base_url: str, model: str) -> bool:
    """判定是否走 Anthropic Messages API。

    触发条件（任一即可）：
    - base_url 指向官方/代理 anthropic 域名
    - model 以 claude- 开头（兼容用户写 https://api.anthropic.com 不带 /v1 的场景）

    走 Anthropic 原生路径可避免向 anthropic.com/chat/completions 发请求时遇到 404。
    """
    bu = (base_url or "").lower()
    m = (model or "").lower()
    if "anthropic.com" in bu:
        return True
    if m.startswith("claude-") or m.startswith("claude."):
        return True
    return False


def _split_system_messages(
    messages: List[Dict[str, str]],
) -> tuple[Optional[str], List[Dict[str, str]]]:
    """Anthropic 协议把 system prompt 单独传，不能混在 messages 数组里。"""
    sys_parts: List[str] = []
    other: List[Dict[str, str]] = []
    for m in messages:
        if m.get("role") == "system":
            content = (m.get("content") or "").strip()
            if content:
                sys_parts.append(content)
        else:
            other.append({"role": m["role"], "content": m["content"]})
    system_text = "\n\n".join(sys_parts) if sys_parts else None
    return system_text, other


def _anthropic_chat_completion(
    model_config: "ResolvedModelConfig",
    messages: List[Dict[str, str]],
    *,
    timeout: int,
    temperature: Optional[float],
    max_tokens: Optional[int],
) -> str:
    """走 Anthropic Messages API 完成 chat 调用，并以 OpenAI-style 形态记录日志。"""
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "anthropic SDK 未安装；请在 backend/requirements.txt 中加入 "
            "anthropic>=0.40.0,<1.0 并 pip install -r backend/requirements.txt"
        ) from exc

    base_url = (model_config.base_url or "").strip()
    client_kwargs: Dict[str, Any] = {"api_key": model_config.api_key, "timeout": timeout}
    # 仅在用户使用非默认 endpoint（如代理）时才显式注入 base_url
    if base_url and "api.anthropic.com" not in base_url.lower():
        client_kwargs["base_url"] = base_url
    client = Anthropic(**client_kwargs)

    system_text, user_messages = _split_system_messages(messages)

    payload: Dict[str, Any] = {
        "model": model_config.model_name,
        "max_tokens": max_tokens if max_tokens is not None else model_config.max_tokens,
        "messages": user_messages,
    }
    if system_text:
        payload["system"] = system_text
    eff_temp = temperature if temperature is not None else model_config.temperature
    if eff_temp is not None:
        payload["temperature"] = eff_temp

    logger.info(
        "[copy_gen][llm] (anthropic) call model=%s base_url=%s msgs=%d temp=%.2f max_tokens=%d",
        model_config.model_name,
        base_url or "(default)",
        len(user_messages),
        eff_temp if eff_temp is not None else -1.0,
        payload["max_tokens"],
    )
    request_log: Dict[str, Any] = {
        "provider": "anthropic",
        "model": payload["model"],
        "max_tokens": payload["max_tokens"],
        "messages": user_messages,
    }
    if system_text:
        request_log["system"] = system_text
    if "temperature" in payload:
        request_log["temperature"] = payload["temperature"]
    logger.info("[copy_gen][llm] request_body=%s", _safe_dump(request_log))

    t0 = time.perf_counter()
    try:
        response = client.messages.create(**payload)
    except Exception as exc:
        logger.exception(
            "[copy_gen][llm] (anthropic) request failed after %.2fs: %s",
            time.perf_counter() - t0,
            exc,
        )
        raise
    elapsed = time.perf_counter() - t0

    # Anthropic 用 input_tokens / output_tokens，归一化成 OpenAI-style key
    usage_obj = getattr(response, "usage", None)
    in_tok = getattr(usage_obj, "input_tokens", None) if usage_obj else None
    out_tok = getattr(usage_obj, "output_tokens", None) if usage_obj else None
    total_tok = (
        (in_tok or 0) + (out_tok or 0) if (in_tok is not None or out_tok is not None) else None
    )

    content_blocks = []
    text_parts: List[str] = []
    for block in getattr(response, "content", []) or []:
        btype = getattr(block, "type", None)
        btext = getattr(block, "text", None)
        content_blocks.append({"type": btype, "text": btext})
        if btype == "text" and btext:
            text_parts.append(btext)

    serialized: Dict[str, Any] = {
        "provider": "anthropic",
        "id": getattr(response, "id", None),
        "model": getattr(response, "model", None),
        "type": getattr(response, "type", None),
        "role": getattr(response, "role", None),
        "stop_reason": getattr(response, "stop_reason", None),
        "stop_sequence": getattr(response, "stop_sequence", None),
        "content": content_blocks,
        "usage": {
            "prompt_tokens": in_tok,
            "completion_tokens": out_tok,
            "total_tokens": total_tok,
        },
    }
    logger.info(
        "[copy_gen][llm] usage prompt=%s completion=%s total=%s elapsed=%.2fs",
        in_tok, out_tok, total_tok, elapsed,
    )
    logger.info("[copy_gen][llm] response_body=%s", _safe_dump(serialized))

    content = "".join(text_parts).strip()
    if not content:
        raise RuntimeError("Anthropic 返回 content 为空")
    return content


def chat_completion(
    model_config: ResolvedModelConfig,
    messages: List[Dict[str, str]],
    *,
    timeout: int = 120,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    extra_body: Optional[Dict[str, Any]] = None,
) -> str:
    """调用 chat.completions.create 并返回纯字符串 content。

    Raises:
        RuntimeError: 当 openai SDK 未安装或返回空 content。
        Exception: 透传底层 SDK 抛出的网络 / 鉴权 / 配额错误。
    """
    if not model_config.api_key:
        raise RuntimeError("未配置 api_key，无法调用 LLM")

    # 路由：Anthropic API 不兼容 OpenAI 的 /chat/completions —— 必须走原生 SDK，
    # 否则向 api.anthropic.com 发 chat.completions 会得到 404 NotFoundError。
    if _is_anthropic_target(model_config.base_url, model_config.model_name):
        return _anthropic_chat_completion(
            model_config,
            messages,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    client = _build_client(
        base_url=model_config.base_url or "",
        api_key=model_config.api_key,
        timeout=timeout,
    )

    payload: Dict[str, Any] = {
        "model": model_config.model_name,
        "messages": messages,
        "temperature": temperature if temperature is not None else model_config.temperature,
        "max_tokens": max_tokens if max_tokens is not None else model_config.max_tokens,
    }
    if extra_body:
        payload["extra_body"] = extra_body

    logger.info(
        "[copy_gen][llm] call model=%s base_url=%s msgs=%d temp=%.2f max_tokens=%d",
        model_config.model_name,
        model_config.base_url or "(default)",
        len(messages),
        payload["temperature"],
        payload["max_tokens"],
    )
    # 完整 prompt request body —— 不含 api_key（client 已携带），便于复现/调试
    request_log = {
        "model": payload["model"],
        "temperature": payload["temperature"],
        "max_tokens": payload["max_tokens"],
        "messages": messages,
    }
    if extra_body:
        request_log["extra_body"] = extra_body
    logger.info("[copy_gen][llm] request_body=%s", _safe_dump(request_log))

    t0 = time.perf_counter()
    try:
        response = client.chat.completions.create(**payload)
    except Exception as exc:
        logger.exception(
            "[copy_gen][llm] request failed after %.2fs: %s",
            time.perf_counter() - t0,
            exc,
        )
        raise
    elapsed = time.perf_counter() - t0

    serialized = _serialize_response(response)
    usage = serialized.get("usage") or {}
    logger.info(
        "[copy_gen][llm] usage prompt=%s completion=%s total=%s elapsed=%.2fs",
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        elapsed,
    )
    logger.info("[copy_gen][llm] response_body=%s", _safe_dump(serialized))

    if not response or not getattr(response, "choices", None):
        raise RuntimeError("LLM 返回空 choices")

    choice = response.choices[0]
    message = getattr(choice, "message", None)
    if not message:
        raise RuntimeError("LLM 返回空 message")

    content = getattr(message, "content", None)
    if not content:
        raise RuntimeError("LLM 返回 content 为空")

    return content


def build_messages(
    user_prompt: str,
    *,
    system_prompt: Optional[str] = None,
    agent_system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """组装 OpenAI chat messages。

    顺序：ModelConfig.system_prompt → Agent.system_prompt → user prompt
    任一为空则跳过。
    """
    out: List[Dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        out.append({"role": "system", "content": system_prompt.strip()})
    if agent_system_prompt and agent_system_prompt.strip():
        out.append({"role": "system", "content": agent_system_prompt.strip()})
    out.append({"role": "user", "content": user_prompt})
    return out
