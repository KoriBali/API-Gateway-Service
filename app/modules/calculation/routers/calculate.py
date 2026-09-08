from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import CurrentUser, require_roles
from app.services.calculation import forward
from app.utils.response import success_response
from app.utils.evaluation import (
    EvaluationResult,
    EvaluationGroup,
    EvaluationSection,
    EvaluationRow,
)
from app.modules.calculation.schemas import CalculateRequest

routerCalculate = APIRouter(prefix="/api/calculate", tags=["Calculation"])

_ANY_ROLE = require_roles("superadmin", "admin", "drafter")


def _stub_result() -> EvaluationResult:
    # TODO(calc-stub): placeholder - GANTI dengan hasil calc-service asli.
    # Nilai sengaja dibuat jelas-jelas dummy agar tidak dikira hasil valid.
    row = EvaluationRow(no=1, description="", safety_factor=0.9, status="ok")
    section = EvaluationSection(
        key="direct_wind_a", label="Direct Wind Condition A", rows=[row]
    )
    group = EvaluationGroup(name="Pole 1", status="ok", sections=[section])
    return EvaluationResult(status="ok", groups=[group])


@routerCalculate.post("")
async def calculate(
    payload: CalculateRequest,
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    # tidak ada get_db di sini. endpoint ini stateless.
    if settings.calc_stub_mode:
        result = _stub_result()
    else:
        # TODO(calc-stub): sesuaikan path & bentuk payload dengan calc-service asli.
        forwarded = await forward("/api/calculate", payload)
        result = forwarded.data  # ForwarderResult.data

    return success_response(data=result, message="Calculation completed")