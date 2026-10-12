from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.database.models.intake import BrandLine
from app.modules.intake.repository import ProjectRepository
from app.modules.intake.schemas import ProjectCreate, ProjectRead

routerProject = APIRouter(prefix="/api/projects", tags=["Projects"])

# Project = identitas penomoran DataBank, tidak punya department. Semua role boleh baca/buat.
_ANY_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Read =====
@routerProject.get("")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
    request_form: BrandLine | None = Query(default=None, alias="requestForm"),
    scope_code: str | None = Query(default=None, alias="scopeCode"),
    pj_no: str | None = Query(default=None, alias="pjNo"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await ProjectRepository.list_filtered(
        db,
        request_form=request_form,
        scope_code=scope_code,
        pj_no=pj_no,
        limit=limit,
        offset=offset,
    )
    items = [ProjectRead.model_validate(p) for p in rows]
    return success_response(
        data={"items": items, "total": total, "limit": limit, "offset": offset},
        message="Projects retrieved",
    )


@routerProject.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    project = await ProjectRepository.get_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return success_response(
        data=ProjectRead.model_validate(project),
        message="Project retrieved",
    )



# ===== Create =====
@routerProject.post("")
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    existing = await ProjectRepository.find_by_identity(
        db,
        request_form=payload.request_form,
        scope_code=payload.scope_code,
        pj_no=payload.pj_no,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A project with the same identity already exists",
                "existingProjectId": existing.id,
            },
        )

    project = await ProjectRepository.create(db, payload)
    return success_response(
        data=ProjectRead.model_validate(project),
        status_code=status.HTTP_201_CREATED,
        message="Project created",
    )