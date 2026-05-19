"""Qwen3-TTS `content|emotion|speed` 行解析与序列化。

仅保留 bzyagent `src/voice_config.py` 中我们用得到的核心 API：
- VoiceConfig.parse(text)   — 解析单行
- VoiceConfig.create(...)   — 从字段构造
- VoiceConfig.to_string()   — 序列化回 |-分隔字符串
- parse_lines(multiline)    — 多行解析（每行一个段落）

注：bzyagent 同时维护了「Qwen3-TTS 一行式」与「旧三行式」两种格式，我们只
需要一行式（content|emotion|speed 或 content|combined）即可，因为 generator
始终要求 LLM 输出一行式。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# 用于把 LLM 偶尔吐出的 emoji 清理掉（来自 bzyagent generator._remove_emoji）
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def remove_emoji(text: str) -> str:
    """剔除常见 emoji 字符。"""
    return _EMOJI_RE.sub("", text or "")


@dataclass
class VoiceConfig:
    """单段语音配置：`content|emotion|speed`。

    `emotion` 与 `speed` 历史上是分开的两个字段，但 Qwen3-TTS instruct 通常把
    它们合并成一句自然语言，因此我们额外提供 `combined`（= 第二段之后的全部
    内容）供前端展示和向 TTS 接口传值。
    """

    content: str = ""
    emotion: str = ""
    speed: str = ""
    original_text: str = ""
    combined: str = field(default="")  # = emotion+speed 合并后的 instruct 字符串

    # ── parse / create / serialize ───────────────────────────────────────

    @classmethod
    def parse(cls, text: str) -> Optional["VoiceConfig"]:
        """解析单行 `内容|情绪|语速` 或 `内容|合并 instruct`。

        - 第一段为 content
        - 第二段为 emotion（若有）
        - 第三段为 speed（若有）
        - 同时把第二段之后整段保存到 combined，方便直接喂给 Qwen3-TTS instruct
        """
        if not text:
            return None
        line = text.strip()
        if not line:
            return None

        parts = line.split("|")
        cfg = cls()
        cfg.original_text = line
        cfg.content = parts[0].strip()
        if len(parts) >= 2:
            cfg.emotion = parts[1].strip()
        if len(parts) >= 3:
            cfg.speed = parts[2].strip()
        if len(parts) >= 2:
            # combined = | 右侧所有部分原样合并（保留 | 作为分隔），
            # 与 Qwen3-TTS 的一行式 instruct 用法对齐
            cfg.combined = "|".join(p.strip() for p in parts[1:]).strip()
        return cfg

    @classmethod
    def create(cls, content: str, emotion: str = "", speed: str = "") -> "VoiceConfig":
        cfg = cls(content=content.strip(), emotion=emotion.strip(), speed=speed.strip())
        bits = [p for p in (cfg.emotion, cfg.speed) if p]
        cfg.combined = " ".join(bits)
        cfg.original_text = cfg.to_string()
        return cfg

    def to_string(self) -> str:
        parts: List[str] = [self.content]
        if self.combined:
            parts.append(self.combined)
        else:
            if self.emotion:
                parts.append(self.emotion)
            if self.speed:
                parts.append(self.speed)
        return "|".join(parts)

    # ── dict 转换（供 Pydantic VoiceLineOut 用） ─────────────────────────

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "emotion": self.emotion or self.combined,
            "speed": self.speed,
            "original_text": self.original_text,
        }


def parse_lines(text: str, *, strip_emoji: bool = True) -> List[VoiceConfig]:
    """把多行 LLM 输出解析为 VoiceConfig 列表。

    - 空行 / markdown 围栏（```...```）会被跳过
    - 没有 `|` 的行也被收录（content-only，emotion/speed 为空）
    """
    if not text:
        return []
    if strip_emoji:
        text = remove_emoji(text)

    out: List[VoiceConfig] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if "|" in line:
            cfg = VoiceConfig.parse(line)
        else:
            cfg = VoiceConfig.create(content=line)
        if cfg and cfg.content:
            out.append(cfg)
    return out


def join_plain_text(configs: List[VoiceConfig]) -> str:
    """提取 content 拼接（用于纯文本展示 / 字数统计）。"""
    return "\n".join(c.content for c in configs if c.content)


def join_qwen3_tts_text(configs: List[VoiceConfig]) -> str:
    """重新组装为 `内容|instruct` 多行字符串（Qwen3-TTS 直接可用）。"""
    return "\n".join(c.to_string() for c in configs if c.content)
