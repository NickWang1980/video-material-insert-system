"""Agent / Rule / Knowledge CRUD + system prompt 组装。

bzyagent 的 `agent_system.py` 把 Agent / 规则 / 知识库都持久化在 JSON 文件
里，移植到本项目后改为 SQLAlchemy 关系表（CopyGenAgent / CopyGenRule /
CopyGenKnowledge）。算法（规则按 priority 排序、positive 与 negative 分组、
知识库以 `——` 分隔追加）保持一致。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ...models.copy_gen import CopyGenAgent, CopyGenKnowledge, CopyGenRule
from ...schemas.copy_gen import (
    AgentCreate,
    AgentUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    RuleCreate,
    RuleUpdate,
)

logger = logging.getLogger(__name__)


# 防止 system prompt 在极端情况下把 LLM 的上下文吃光。一旦超过此阈值，会被
# 截断并写一条 WARNING 日志。后续 Phase 可以引入 LLM 自总结。
MAX_SYSTEM_PROMPT_CHARS = 12000


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

def list_agents(db: Session) -> List[CopyGenAgent]:
    return list(db.query(CopyGenAgent).order_by(CopyGenAgent.id.asc()).all())


def get_agent(db: Session, agent_id: int) -> Optional[CopyGenAgent]:
    return db.query(CopyGenAgent).filter(CopyGenAgent.id == agent_id).first()


def create_agent(db: Session, payload: AgentCreate) -> CopyGenAgent:
    now = datetime.utcnow()
    obj = CopyGenAgent(
        name=payload.name,
        description=payload.description,
        platform=payload.platform,
        industry=payload.industry,
        default_template=payload.default_template,
        default_target_words=payload.default_target_words,
        default_tolerance=payload.default_tolerance,
        default_script_type=payload.default_script_type or "single",
        model_config_id=payload.model_config_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_agent(
    db: Session, agent_id: int, payload: AgentUpdate
) -> Optional[CopyGenAgent]:
    obj = get_agent(db, agent_id)
    if not obj:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_agent(db: Session, agent_id: int) -> bool:
    obj = get_agent(db, agent_id)
    if not obj:
        return False
    # rules / knowledge 通过 ON DELETE CASCADE 由数据库清理（SQLite 需开启
    # foreign_keys，但 SQLAlchemy create_engine 没显式开。为稳妥也手动清。）
    db.query(CopyGenRule).filter(CopyGenRule.agent_id == agent_id).delete()
    db.query(CopyGenKnowledge).filter(CopyGenKnowledge.agent_id == agent_id).delete()
    db.delete(obj)
    db.commit()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────

def list_rules(db: Session, agent_id: int) -> List[CopyGenRule]:
    return list(
        db.query(CopyGenRule)
        .filter(CopyGenRule.agent_id == agent_id)
        .order_by(CopyGenRule.priority.desc(), CopyGenRule.id.asc())
        .all()
    )


def get_rule(db: Session, agent_id: int, rule_id: int) -> Optional[CopyGenRule]:
    return (
        db.query(CopyGenRule)
        .filter(CopyGenRule.agent_id == agent_id, CopyGenRule.id == rule_id)
        .first()
    )


def create_rule(db: Session, agent_id: int, payload: RuleCreate) -> CopyGenRule:
    now = datetime.utcnow()
    obj = CopyGenRule(
        agent_id=agent_id,
        category=payload.category or "general",
        content=payload.content,
        original_content=payload.original_content,
        rule_type=payload.rule_type or "positive",
        priority=payload.priority or 0,
        source=payload.source or "user",
        created_at=now,
        updated_at=now,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_rule(
    db: Session, agent_id: int, rule_id: int, payload: RuleUpdate
) -> Optional[CopyGenRule]:
    obj = get_rule(db, agent_id, rule_id)
    if not obj:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_rule(db: Session, agent_id: int, rule_id: int) -> bool:
    obj = get_rule(db, agent_id, rule_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge
# ─────────────────────────────────────────────────────────────────────────────

def list_knowledge(db: Session, agent_id: int) -> List[CopyGenKnowledge]:
    return list(
        db.query(CopyGenKnowledge)
        .filter(CopyGenKnowledge.agent_id == agent_id)
        .order_by(CopyGenKnowledge.id.asc())
        .all()
    )


def get_knowledge(
    db: Session, agent_id: int, kid: int
) -> Optional[CopyGenKnowledge]:
    return (
        db.query(CopyGenKnowledge)
        .filter(CopyGenKnowledge.agent_id == agent_id, CopyGenKnowledge.id == kid)
        .first()
    )


def create_knowledge(
    db: Session, agent_id: int, payload: KnowledgeCreate
) -> CopyGenKnowledge:
    obj = CopyGenKnowledge(
        agent_id=agent_id,
        category=payload.category or "general",
        title=payload.title,
        content=payload.content,
        status=payload.status or "active",
        status_note=payload.status_note or "",
        created_at=datetime.utcnow(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_knowledge(
    db: Session, agent_id: int, kid: int, payload: KnowledgeUpdate
) -> Optional[CopyGenKnowledge]:
    obj = get_knowledge(db, agent_id, kid)
    if not obj:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_knowledge(db: Session, agent_id: int, kid: int) -> bool:
    obj = get_knowledge(db, agent_id, kid)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Summary helpers（→ Pydantic AgentSummaryOut）
# ─────────────────────────────────────────────────────────────────────────────

def agent_summary(
    db: Session, agent: CopyGenAgent
) -> Tuple[int, int]:
    rule_count = (
        db.query(CopyGenRule).filter(CopyGenRule.agent_id == agent.id).count()
    )
    knowledge_count = (
        db.query(CopyGenKnowledge)
        .filter(CopyGenKnowledge.agent_id == agent.id)
        .count()
    )
    return rule_count, knowledge_count


# ─────────────────────────────────────────────────────────────────────────────
# System prompt 组装（核心算法）
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(
    db: Session,
    agent: CopyGenAgent,
    *,
    extra_instructions: Optional[str] = None,
) -> str:
    """把 Agent 描述 + 规则 + 知识库拼成 system prompt。

    输出结构：
    ```
    【角色定位】Agent.name — Agent.description
    【平台】xx
    【行业】xx
    【写作规则】
    1. 内容（priority=...）
    2. ...
    【避免事项】（rule_type=negative）
    - ...
    【背景知识】
    ## title
    content
    ---
    【其他指令】
    extra_instructions
    ```
    """
    parts: List[str] = []

    head = f"【角色定位】{agent.name}"
    if agent.description:
        head += f" — {agent.description}"
    parts.append(head)

    if agent.platform:
        parts.append(f"【目标平台】{agent.platform}")
    if agent.industry:
        parts.append(f"【行业领域】{agent.industry}")

    rules = list_rules(db, agent.id)  # 已按 priority 倒序
    positives = [r for r in rules if (r.rule_type or "positive") == "positive"]
    negatives = [r for r in rules if r.rule_type == "negative"]

    if positives:
        lines = ["【写作规则】"]
        for i, r in enumerate(positives, 1):
            tag = f"[{r.category}]" if r.category and r.category != "general" else ""
            lines.append(f"{i}. {tag}{r.content}")
        parts.append("\n".join(lines))

    if negatives:
        lines = ["【避免事项】"]
        for r in negatives:
            tag = f"[{r.category}]" if r.category and r.category != "general" else ""
            lines.append(f"- {tag}{r.content}")
        parts.append("\n".join(lines))

    knowledge = list_knowledge(db, agent.id)
    active_knowledge = [k for k in knowledge if (k.status or "active") == "active"]
    if active_knowledge:
        chunks: List[str] = ["【背景知识】"]
        for k in active_knowledge:
            tag = f"({k.category})" if k.category and k.category != "general" else ""
            chunks.append(f"## {k.title}{tag}\n{k.content}")
        parts.append("\n---\n".join(chunks))

    if extra_instructions and extra_instructions.strip():
        parts.append(f"【其他指令】\n{extra_instructions.strip()}")

    text = "\n\n".join(parts)
    if len(text) > MAX_SYSTEM_PROMPT_CHARS:
        logger.warning(
            "[copy_gen] system prompt %d chars > %d, truncating",
            len(text),
            MAX_SYSTEM_PROMPT_CHARS,
        )
        text = text[:MAX_SYSTEM_PROMPT_CHARS] + "\n…（已截断）"
    return text
