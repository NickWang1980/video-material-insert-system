from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models.material import Material
from ..models.rough_cut_project import RoughCutProject
from ..models.task import Task


router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def api_stats(db: Session = Depends(get_db)):
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    processing_tasks = db.query(Task).filter(Task.status == "processing").count()
    failed_tasks = db.query(Task).filter(Task.status == "failed").count()
    total_materials = db.query(Material).count()

    total_rough_cut = db.query(RoughCutProject).count()
    processing_rough_cut = (
        db.query(RoughCutProject).filter(RoughCutProject.status == "processing").count()
    )
    completed_rough_cut = (
        db.query(RoughCutProject)
        .filter((RoughCutProject.phase == "completed") | (RoughCutProject.status == "ready"))
        .count()
    )

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "processing_tasks": processing_tasks,
        "failed_tasks": failed_tasks,
        "total_materials": total_materials,
        "total_rough_cut_projects": total_rough_cut,
        "processing_rough_cut_projects": processing_rough_cut,
        "completed_rough_cut_projects": completed_rough_cut,
    }
