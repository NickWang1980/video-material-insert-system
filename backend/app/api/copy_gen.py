"""Copy Gen API routes (`/api/copy-gen`).

Phase-1 完整 REST 表面：
- Enums
- ModelConfig CRUD + test
- Agent CRUD + Rules CRUD + Knowledge CRUD + agent generate
- Quick generate
- History list + delete
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..schemas.copy_gen import (
    AgentCreate,
    AgentDetailOut,
    AgentSummaryOut,
    AgentUpdate,
    EnumItem,
    EnumsResponse,
    GenerateRequest,
    GenerateResponse,
    HistoryListResponse,
    HistoryOut,
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeUpdate,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
    ModelTestResponse,
    OkResponse,
    RuleCreate,
    RuleOut,
    RuleUpdate,
    TemplateItem,
)
from ..services.copy_gen import (
    agent_service,
    generator_service,
    model_config_service,
)
from ..services.copy_gen import templates as cg_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copy-gen", tags=["copy_gen"])


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/enums", response_model=EnumsResponse)
def get_enums() -> EnumsResponse:
    """前端进入页面后第一时间拉一次：拿到所有下拉枚举。"""
    platforms = [
        EnumItem(code=p, name=p, description=tone.get("tone", ""))
        for p, tone in cg_templates.PLATFORM_TONES.items()
    ]
    templates = [
        TemplateItem(code=code, name=t["name"], description=t["description"])
        for code, t in cg_templates.TEMPLATES.items()
    ]
    script_types = [
        EnumItem(code=code, name=v["name"], description=v.get("description"))
        for code, v in cg_templates.SCRIPT_TYPES.items()
    ]
    return EnumsResponse(
        platforms=platforms,
        templates=templates,
        script_types=script_types,
        emotions=cg_templates.get_all_emotions(),
        speeds=cg_templates.get_all_speeds(),
        rule_categories=cg_templates.RULE_CATEGORIES,
        knowledge_categories=cg_templates.KNOWLEDGE_CATEGORIES,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ModelConfigs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/models", response_model=List[ModelConfigOut])
def list_model_configs(db: Session = Depends(get_db)) -> List[ModelConfigOut]:
    return [ModelConfigOut(**model_config_service.to_out_dict(o))
            for o in model_config_service.list_configs(db)]


@router.post("/models", response_model=ModelConfigOut)
def create_model_config(
    payload: ModelConfigCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ModelConfigOut:
    obj = model_config_service.create_config(db, payload, settings)
    return ModelConfigOut(**model_config_service.to_out_dict(obj))


@router.put("/models/{config_id}", response_model=ModelConfigOut)
def update_model_config(
    config_id: int,
    payload: ModelConfigUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ModelConfigOut:
    obj = model_config_service.update_config(db, config_id, payload, settings)
    if not obj:
        raise HTTPException(status_code=404, detail=f"ModelConfig id={config_id} 不存在")
    return ModelConfigOut(**model_config_service.to_out_dict(obj))


@router.delete("/models/{config_id}", response_model=OkResponse)
def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
) -> OkResponse:
    ok = model_config_service.delete_config(db, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"ModelConfig id={config_id} 不存在")
    return OkResponse(ok=True)


@router.post("/models/{config_id}/test", response_model=ModelTestResponse)
def test_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ModelTestResponse:
    obj = model_config_service.get_config(db, config_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"ModelConfig id={config_id} 不存在")
    resolved = model_config_service.resolve(obj, settings)
    if not resolved.api_key:
        return ModelTestResponse(
            ok=False, message="api_key 解密失败或为空，请重新保存", latency_ms=0
        )
    return model_config_service.test_connectivity(resolved, settings)


# ─────────────────────────────────────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────────────────────────────────────

def _agent_to_summary(db: Session, agent) -> AgentSummaryOut:
    rule_count, knowledge_count = agent_service.agent_summary(db, agent)
    return AgentSummaryOut(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        platform=agent.platform,
        industry=agent.industry,
        default_template=agent.default_template,
        default_script_type=agent.default_script_type or "single",
        model_config_id=agent.model_config_id,
        is_active=bool(agent.is_active),
        rule_count=rule_count,
        knowledge_count=knowledge_count,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _agent_to_detail(db: Session, agent) -> AgentDetailOut:
    rules = [RuleOut.model_validate(r) for r in agent_service.list_rules(db, agent.id)]
    knowledge = [
        KnowledgeOut.model_validate(k) for k in agent_service.list_knowledge(db, agent.id)
    ]
    return AgentDetailOut(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        platform=agent.platform,
        industry=agent.industry,
        default_template=agent.default_template,
        default_target_words=agent.default_target_words,
        default_tolerance=agent.default_tolerance,
        default_script_type=agent.default_script_type or "single",
        model_config_id=agent.model_config_id,
        is_active=bool(agent.is_active),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        rules=rules,
        knowledge=knowledge,
    )


@router.get("/agents", response_model=List[AgentSummaryOut])
def list_agents(db: Session = Depends(get_db)) -> List[AgentSummaryOut]:
    return [_agent_to_summary(db, a) for a in agent_service.list_agents(db)]


@router.post("/agents", response_model=AgentDetailOut)
def create_agent(
    payload: AgentCreate, db: Session = Depends(get_db)
) -> AgentDetailOut:
    obj = agent_service.create_agent(db, payload)
    return _agent_to_detail(db, obj)


@router.get("/agents/{agent_id}", response_model=AgentDetailOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)) -> AgentDetailOut:
    obj = agent_service.get_agent(db, agent_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")
    return _agent_to_detail(db, obj)


@router.put("/agents/{agent_id}", response_model=AgentDetailOut)
def update_agent(
    agent_id: int, payload: AgentUpdate, db: Session = Depends(get_db)
) -> AgentDetailOut:
    obj = agent_service.update_agent(db, agent_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")
    return _agent_to_detail(db, obj)


@router.delete("/agents/{agent_id}", response_model=OkResponse)
def delete_agent(agent_id: int, db: Session = Depends(get_db)) -> OkResponse:
    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")
    return OkResponse(ok=True)


@router.post("/agents/{agent_id}/generate", response_model=GenerateResponse)
def agent_generate(
    agent_id: int,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> GenerateResponse:
    return generator_service.generate_with_agent(agent_id, payload, db, settings)


# ─── Rules ───────────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/rules", response_model=RuleOut)
def create_rule(
    agent_id: int, payload: RuleCreate, db: Session = Depends(get_db)
) -> RuleOut:
    if not agent_service.get_agent(db, agent_id):
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")
    obj = agent_service.create_rule(db, agent_id, payload)
    return RuleOut.model_validate(obj)


@router.put("/agents/{agent_id}/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    agent_id: int,
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
) -> RuleOut:
    obj = agent_service.update_rule(db, agent_id, rule_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Rule id={rule_id} 不存在")
    return RuleOut.model_validate(obj)


@router.delete("/agents/{agent_id}/rules/{rule_id}", response_model=OkResponse)
def delete_rule(
    agent_id: int, rule_id: int, db: Session = Depends(get_db)
) -> OkResponse:
    if not agent_service.delete_rule(db, agent_id, rule_id):
        raise HTTPException(status_code=404, detail=f"Rule id={rule_id} 不存在")
    return OkResponse(ok=True)


# ─── Knowledge ───────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/knowledge", response_model=KnowledgeOut)
def create_knowledge(
    agent_id: int, payload: KnowledgeCreate, db: Session = Depends(get_db)
) -> KnowledgeOut:
    if not agent_service.get_agent(db, agent_id):
        raise HTTPException(status_code=404, detail=f"Agent id={agent_id} 不存在")
    obj = agent_service.create_knowledge(db, agent_id, payload)
    return KnowledgeOut.model_validate(obj)


@router.put("/agents/{agent_id}/knowledge/{kid}", response_model=KnowledgeOut)
def update_knowledge(
    agent_id: int,
    kid: int,
    payload: KnowledgeUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeOut:
    obj = agent_service.update_knowledge(db, agent_id, kid, payload)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Knowledge id={kid} 不存在")
    return KnowledgeOut.model_validate(obj)


@router.delete("/agents/{agent_id}/knowledge/{kid}", response_model=OkResponse)
def delete_knowledge(
    agent_id: int, kid: int, db: Session = Depends(get_db)
) -> OkResponse:
    if not agent_service.delete_knowledge(db, agent_id, kid):
        raise HTTPException(status_code=404, detail=f"Knowledge id={kid} 不存在")
    return OkResponse(ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Quick generate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
def quick_generate(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> GenerateResponse:
    return generator_service.generate(payload, db, settings)


# ─────────────────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/history", response_model=HistoryListResponse)
def list_history(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    items, total = generator_service.list_history(db, limit=limit, offset=offset)
    return HistoryListResponse(
        items=[HistoryOut(**generator_service.history_to_dict(h)) for h in items],
        total=total,
    )


@router.delete("/history/{history_id}", response_model=OkResponse)
def delete_history(history_id: int, db: Session = Depends(get_db)) -> OkResponse:
    if not generator_service.delete_history(db, history_id):
        raise HTTPException(status_code=404, detail=f"History id={history_id} 不存在")
    return OkResponse(ok=True)
