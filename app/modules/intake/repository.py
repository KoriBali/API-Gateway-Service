from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.intake import (
    BrandLine,
    DatabankProject,
    Request,
    RequestStatus,
    RequestType,
    DesignType,
    RequestClassification,
    RequestSharedDetails,
    RequestYpDetails,
    RequestYsDetails,
    RequestFinish,
)
from app.database.models.calculation import Condition
from app.database.models.master import PoleCategory, Region, DesignStandard, Material
from app.modules.intake.schemas import (
    ProjectCreate,
    RequestCreate,
    RequestUpdate,
    SharedDetailsWrite,
    YpDetailsWrite,
    YsDetailsWrite,
    FinishWrite,
    ConditionsUpdate,
)


_REQUEST_EDITABLE = (
    "project_id", "pole_category_id", "request_no", "pj_no",
    "request_type", "design_type", "request_classification",
    "subject", "request_date", "due_date", "requesting_department_name", "notes",
)

_SHARED_EDITABLE = tuple(SharedDetailsWrite.model_fields)
_YP_EDITABLE = tuple(YpDetailsWrite.model_fields)
_YS_EDITABLE = tuple(YsDetailsWrite.model_fields)
_FINISH_EDITABLE = tuple(FinishWrite.model_fields)
_CONDITIONS_EDITABLE = ("design_standard_id", "wind_speed", "air_density")


def _apply(row, data: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        if field in data:
            setattr(row, field, data[field])


def _dump(payload) -> dict:
    """Field yang dikirim client saja; payload kosong (tidak dikirim) = dict kosong."""
    return payload.model_dump(exclude_unset=True) if payload is not None else {}



# ===== Project =====
class ProjectRepository:

    @staticmethod
    async def get_by_id(db: AsyncSession, project_id: str) -> DatabankProject | None:
        result = await db.execute(select(DatabankProject).where(DatabankProject.id == project_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def find_by_identity(
        db: AsyncSession, *, request_form: BrandLine, scope_code: str, pj_no: str,
    ) -> DatabankProject | None:
        result = await db.execute(
            select(DatabankProject).where(
                DatabankProject.request_form == request_form,
                DatabankProject.scope_code == scope_code,
                DatabankProject.pj_no == pj_no,
                DatabankProject.is_placeholder.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_filtered(
        db: AsyncSession,
        *,
        request_form: BrandLine | None = None,
        scope_code: str | None = None,
        pj_no: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DatabankProject], int]:
        stmt = select(DatabankProject)
        if request_form is not None:
            stmt = stmt.where(DatabankProject.request_form == request_form)
        if scope_code is not None:
            stmt = stmt.where(DatabankProject.scope_code == scope_code)
        if pj_no is not None:
            stmt = stmt.where(DatabankProject.pj_no == pj_no)

        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

        stmt = stmt.order_by(
            DatabankProject.request_form, DatabankProject.scope_code, DatabankProject.pj_no,
        ).limit(limit).offset(offset)
        rows = list((await db.execute(stmt)).scalars().all())
        return rows, int(total or 0)

    @staticmethod
    async def create(db: AsyncSession, payload: ProjectCreate) -> DatabankProject:
        project = DatabankProject(
            request_form=payload.request_form,
            scope_code=payload.scope_code,
            pj_no=payload.pj_no,
            is_placeholder=False,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project



# ===== Request =====
class RequestRepository:

    @staticmethod
    async def get_by_id(db: AsyncSession, request_id: str) -> Request | None:
        result = await db.execute(select(Request).where(Request.id == request_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_detail(db: AsyncSession, request_id: str) -> Request | None:
        """Request + tabel bersama + ekstensi form + finish + conditions."""
        result = await db.execute(
            select(Request)
            .where(Request.id == request_id)
            .options(
                selectinload(Request.shared_details),
                selectinload(Request.yp_details),
                selectinload(Request.ys_details),
                selectinload(Request.finish),
                selectinload(Request.conditions),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def pole_category_exists(db: AsyncSession, pole_category_id: str) -> bool:
        found = await db.scalar(
            select(PoleCategory.id).where(PoleCategory.id == pole_category_id)
        )
        return found is not None

    @staticmethod
    async def region_exists(db: AsyncSession, region_id: str) -> bool:
        found = await db.scalar(select(Region.id).where(Region.id == region_id))
        return found is not None

    @staticmethod
    async def design_standard_exists(db: AsyncSession, design_standard_id: str) -> bool:
        found = await db.scalar(
            select(DesignStandard.id).where(DesignStandard.id == design_standard_id)
        )
        return found is not None

    @staticmethod
    async def material_exists(db: AsyncSession, material_id: str) -> bool:
        found = await db.scalar(select(Material.id).where(Material.id == material_id))
        return found is not None

    @staticmethod
    async def list_by_request_no(
        db: AsyncSession, request_no: str, *, exclude_request_id: str | None = None,
    ) -> list[Request]:
        """Semua request ber-request_no sama (kedua form), TANPA scope peran. Router yang menyaring."""
        stmt = select(Request).where(Request.request_no == request_no)

        if exclude_request_id is not None:
            stmt = stmt.where(Request.id != exclude_request_id)
        stmt = stmt.order_by(Request.created_at)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def list_scoped(
        db: AsyncSession,
        *,
        role: str,
        actor_id: str,
        actor_department_id: str | None,
        brand_line: BrandLine | None = None,
        project_id: str | None = None,
        request_type: RequestType | None = None,
        request_classification: RequestClassification | None = None,
        design_type: DesignType | None = None,
        pole_category_id: str | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        status: RequestStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Request], int]:
        stmt = select(Request)

        # Scope per Role
        if role == "superadmin":
            pass
        elif role == "admin_department":
            # admin department tanpa department tak dapat melihat data apapun
            if actor_department_id is None:
                return [], 0
            stmt = stmt.where(Request.responsible_department_id == actor_department_id)
        else:
            stmt = stmt.where(Request.created_by_user_id == actor_id)

        # Filter opsional
        if brand_line is not None:
            stmt = stmt.where(Request.brand_line == brand_line)
        if project_id is not None:
            stmt = stmt.where(Request.project_id == project_id)
        if request_type is not None:
            stmt = stmt.where(Request.request_type == request_type)
        if request_classification is not None:
            stmt = stmt.where(Request.request_classification == request_classification)
        if design_type is not None:
            stmt = stmt.where(Request.design_type == design_type)
        if pole_category_id is not None:
            stmt = stmt.where(Request.pole_category_id == pole_category_id)
        if due_from is not None:
            stmt = stmt.where(Request.due_date >= due_from)
        if due_to is not None:
            stmt = stmt.where(Request.due_date <= due_to)
        if status is not None:
            stmt = stmt.where(Request.status == status)

        # Total
        total = await db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )

        # Halaman data
        stmt = stmt.order_by(Request.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        return rows, int(total or 0)

    @staticmethod
    async def create(
        db: AsyncSession,
        payload: RequestCreate,
        *,
        created_by_user_id: str,
        responsible_department_id: str,
    ) -> Request:
        """Intake dalam SATU transaksi (DD G12): request + tabel bersama + ekstensi form
        + finish + conditions. Semua baris anak lahir walau isiannya kosong."""
        req = Request(
            brand_line=payload.brand_line,
            responsible_department_id=responsible_department_id,
            created_by_user_id=created_by_user_id,
            status=RequestStatus.internal,
            **payload.model_dump(
                include=set(_REQUEST_EDITABLE),
            ),
        )
        db.add(req)
        await db.flush()  # butuh req.id untuk baris anak

        db.add(RequestSharedDetails(request_id=req.id, **_dump(payload.shared_details)))
        if payload.brand_line == BrandLine.yp:
            db.add(RequestYpDetails(request_id=req.id, brand_line=BrandLine.yp, **_dump(payload.yp_details)))
        else:
            db.add(RequestYsDetails(request_id=req.id, brand_line=BrandLine.ys, **_dump(payload.ys_details)))
        db.add(RequestFinish(request_id=req.id, **_dump(payload.finish)))
        db.add(Condition(request_id=req.id, **payload.conditions.model_dump()))

        await db.commit()
        return req

    @staticmethod
    async def update(db: AsyncSession, req: Request, payload: RequestUpdate) -> Request:
        _apply(req, payload.model_dump(exclude_unset=True), _REQUEST_EDITABLE)
        await db.commit()
        await db.refresh(req)
        return req
    
    @staticmethod
    async def get_shared_details(db: AsyncSession, request_id: str) -> RequestSharedDetails | None:
        return await db.scalar(
            select(RequestSharedDetails).where(RequestSharedDetails.request_id == request_id)
        )

    @staticmethod
    async def update_shared_details(db: AsyncSession, req: Request, payload: SharedDetailsWrite) -> None:
        row = await RequestRepository.get_shared_details(db, req.id)
        if row is None:
            row = RequestSharedDetails(request_id=req.id)
            db.add(row)
        _apply(row, payload.model_dump(exclude_unset=True), _SHARED_EDITABLE)
        await db.commit()

    @staticmethod
    async def update_yp_details(db: AsyncSession, req: Request, payload: YpDetailsWrite) -> None:
        row = await db.scalar(select(RequestYpDetails).where(RequestYpDetails.request_id == req.id))
        if row is None:
            row = RequestYpDetails(request_id=req.id, brand_line=BrandLine.yp)
            db.add(row)
        _apply(row, payload.model_dump(exclude_unset=True), _YP_EDITABLE)
        await db.commit()

    @staticmethod
    async def update_ys_details(db: AsyncSession, req: Request, payload: YsDetailsWrite) -> None:
        row = await db.scalar(select(RequestYsDetails).where(RequestYsDetails.request_id == req.id))
        if row is None:
            row = RequestYsDetails(request_id=req.id, brand_line=BrandLine.ys)
            db.add(row)
        _apply(row, payload.model_dump(exclude_unset=True), _YS_EDITABLE)
        await db.commit()

    @staticmethod
    async def update_finish(db: AsyncSession, req: Request, payload: FinishWrite) -> None:
        row = await db.scalar(select(RequestFinish).where(RequestFinish.request_id == req.id))
        if row is None:
            row = RequestFinish(request_id=req.id)
            db.add(row)
        _apply(row, payload.model_dump(exclude_unset=True), _FINISH_EDITABLE)
        await db.commit()

    @staticmethod
    async def update_conditions(db: AsyncSession, cond: Condition, payload: ConditionsUpdate) -> None:
        _apply(cond, payload.model_dump(exclude_unset=True), _CONDITIONS_EDITABLE)
        await db.commit()

    @staticmethod
    async def get_conditions(db: AsyncSession, request_id: str) -> Condition | None:
        return await db.scalar(select(Condition).where(Condition.request_id == request_id))

    @staticmethod
    async def delete(db: AsyncSession, req: Request) -> None:
        await db.delete(req)
        await db.commit()