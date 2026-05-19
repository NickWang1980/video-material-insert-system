"""Pydantic v2 schemas for the Copy Gen module.

All request bodies and response models for endpoints under `/api/copy-gen` live
here. The frontend is being built in parallel against these shapes — DO NOT
rename fields without coordinating.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums endpoint
# ─────────────────────────────────────────────────────────────────────────────

class EnumItem(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class TemplateItem(BaseModel):
    code: str
    name: str
    description: str


class EnumsResponse(BaseModel):
    platforms: List[EnumItem]
    templates: List[TemplateItem]
    script_types: List[EnumItem]
    emotions: List[str]
    speeds: List[str]
    rule_categories: List[str]
    knowledge_categories: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# ModelConfig
# ─────────────────────────────────────────────────────────────────────────────

class ModelConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    model_name: str = Field(..., min_length=1, max_length=200)
    base_url: Optional[str] = Field(default="", max_length=500)
    api_key: str = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=200000)
    system_prompt: Optional[str] = None


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: Optional[str] = None  # if None / empty → keep existing
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=200000)
    system_prompt: Optional[str] = None


class ModelConfigOut(BaseModel):
    id: int
    name: str
    model_name: str
    base_url: str
    has_api_key: bool
    temperature: float
    max_tokens: int
    system_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelTestResponse(BaseModel):
    ok: bool
    message: str = ""
    latency_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    category: str = Field(default="general", max_length=80)
    content: str = Field(..., min_length=1)
    original_content: Optional[str] = None
    rule_type: str = Field(default="positive")  # positive | negative
    priority: int = Field(default=0)
    source: str = Field(default="user")  # user | extracted | learned


class RuleUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=80)
    content: Optional[str] = None
    original_content: Optional[str] = None
    rule_type: Optional[str] = None
    priority: Optional[int] = None
    source: Optional[str] = None


class RuleOut(BaseModel):
    id: int
    agent_id: int
    category: str
    content: str
    original_content: Optional[str] = None
    rule_type: str
    priority: int
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeCreate(BaseModel):
    category: str = Field(default="general", max_length=80)
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    status: str = Field(default="active")  # active | outdated | conflict
    status_note: str = Field(default="")


class KnowledgeUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=80)
    title: Optional[str] = Field(default=None, max_length=300)
    content: Optional[str] = None
    status: Optional[str] = None
    status_note: Optional[str] = None


class KnowledgeOut(BaseModel):
    id: int
    agent_id: int
    category: str
    title: str
    content: str
    status: str
    status_note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    platform: Optional[str] = Field(default=None, max_length=60)
    industry: Optional[str] = Field(default=None, max_length=120)
    default_template: Optional[str] = Field(default=None, max_length=60)
    default_target_words: int = Field(default=300, ge=10, le=5000)
    default_tolerance: int = Field(default=50, ge=0, le=1000)
    default_script_type: str = Field(default="single")
    model_config_id: Optional[int] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    platform: Optional[str] = Field(default=None, max_length=60)
    industry: Optional[str] = Field(default=None, max_length=120)
    default_template: Optional[str] = Field(default=None, max_length=60)
    default_target_words: Optional[int] = Field(default=None, ge=10, le=5000)
    default_tolerance: Optional[int] = Field(default=None, ge=0, le=1000)
    default_script_type: Optional[str] = None
    model_config_id: Optional[int] = None
    is_active: Optional[bool] = None


class AgentSummaryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    platform: Optional[str] = None
    industry: Optional[str] = None
    default_template: Optional[str] = None
    default_script_type: str
    model_config_id: Optional[int] = None
    is_active: bool
    rule_count: int
    knowledge_count: int
    created_at: datetime
    updated_at: datetime


class AgentDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    platform: Optional[str] = None
    industry: Optional[str] = None
    default_template: Optional[str] = None
    default_target_words: int
    default_tolerance: int
    default_script_type: str
    model_config_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    rules: List[RuleOut] = []
    knowledge: List[KnowledgeOut] = []


# ─────────────────────────────────────────────────────────────────────────────
# Generate
# ─────────────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    platform: str = Field(default="抖音")
    target_words: int = Field(default=300, ge=10, le=5000)
    tolerance: int = Field(default=50, ge=0, le=1000)
    num_versions: int = Field(default=1, ge=1, le=10)
    template: str = Field(default="product_scenario")
    script_type: str = Field(default="single")
    model_config_id: Optional[int] = None
    model_config_inline: Optional[ModelConfigCreate] = None
    extra_instructions: Optional[str] = None

    # avoid Pydantic v2 protected-namespace warning for fields starting with "model_"
    model_config = ConfigDict(protected_namespaces=())


class VoiceLineOut(BaseModel):
    content: str
    emotion: str = ""
    speed: str = ""
    original_text: str = ""


class VersionOut(BaseModel):
    index: int
    content: str            # plain text (concatenated lines, no | suffix)
    qwen3_tts_text: str     # full `|`-formatted multi-line string
    voice_lines: List[VoiceLineOut]
    word_count: int


class GenerateResponse(BaseModel):
    generation_id: int
    model_used: str
    elapsed_sec: float
    versions: List[VersionOut]
    prompt_used: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────────────────

class HistoryOut(BaseModel):
    id: int
    agent_id: Optional[int] = None
    model_config_id: Optional[int] = None
    payload: Dict[str, Any] = {}
    results: Dict[str, Any] = {}
    created_at: datetime


class HistoryListResponse(BaseModel):
    items: List[HistoryOut]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Misc
# ─────────────────────────────────────────────────────────────────────────────

class OkResponse(BaseModel):
    ok: bool = True
