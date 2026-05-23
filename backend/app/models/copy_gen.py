"""SQLAlchemy ORM models for the Copy Gen (文案生成) module.

Five tables backing Phase-1:
- copy_gen_model_configs : LLM endpoints (OpenAI-compatible). `api_key` is Fernet-encrypted.
- copy_gen_agents        : Agent definition with default params + bound model config.
- copy_gen_rules         : Per-agent rules (positive / negative constraints).
- copy_gen_knowledge     : Per-agent knowledge base entries (joined into system prompt).
- copy_gen_history       : Generation history (payload + results stored as JSON).

JSON columns are leveraged for payload / results to stay schema-flexible — same
pattern used by `task` and `rough_cut_project` models elsewhere in the project.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CopyGenModelConfig(Base):
    """A single LLM endpoint (OpenAI-compatible) the user has saved."""

    __tablename__ = "copy_gen_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Fernet ciphertext — never expose this column to API responses.
    api_key_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CopyGenAgent(Base):
    """An Agent: bundles a model_config with rules + knowledge + default params."""

    __tablename__ = "copy_gen_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_template: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    default_target_words: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    default_tolerance: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    default_script_type: Mapped[str] = mapped_column(String(20), default="single", nullable=False)
    model_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("copy_gen_model_configs.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CopyGenRule(Base):
    """A single rule attached to an Agent. `rule_type` ∈ {positive, negative}."""

    __tablename__ = "copy_gen_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("copy_gen_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(20), default="positive", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CopyGenKnowledge(Base):
    """Knowledge base entry attached to an Agent."""

    __tablename__ = "copy_gen_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("copy_gen_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    status_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CopyGenHistory(Base):
    """One generation = one history row. payload_json + results_json store the
    request and full GenerateResponse so the frontend can render older runs."""

    __tablename__ = "copy_gen_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("copy_gen_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("copy_gen_model_configs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    results_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
