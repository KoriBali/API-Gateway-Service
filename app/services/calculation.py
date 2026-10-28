import httpx
from pydantic import BaseModel
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, Any, Union
from loguru import logger

from app.core.config import settings
from app.core.security import get_internal_service_headers
from app.utils.message_response import get_message_by_unique_code 

# ===== Pemanggil Calculation Service untuk Hitung dan Simpan =====
# Berbeda dari forward(): pemanggil butuh kode status dan body apa adanya
# penolakan payload (4xx) disimpan sebagai run failed, bukan diteruskan sebagai error.
POLE_CALCULATE_PATH = "/api/pole/calculate"


class EngineUnavailable(Exception):
    """Calculation Service tidak terjangkau, atau menjawab selain 200 dan 422.

    Hanya 422 yang berarti payload ditolak (fakta tentang input). 401, 403, 404,
    dan 5xx adalah masalah konfigurasi atau infrastruktur, sehingga tidak menjadi run.
    """


class EngineResponse(BaseModel):
    status_code: int
    body: Any


async def post_engine(path: str, payload: dict) -> EngineResponse:
    url = f"{settings.calc_service_url}{path}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=get_internal_service_headers(),
                timeout=30.0,
            )
    except httpx.RequestError as e:
        logger.error(f"Cannot reach calculation service: {e!r}")
        raise EngineUnavailable(str(e)) from e

    if response.status_code not in (200, 422):
        logger.error(f"Calculation service error: {response.status_code}")
        raise EngineUnavailable(f"HTTP {response.status_code}")

    try:
        body = response.json()
    except ValueError:
        # Jawaban bukan JSON: tidak bisa dipercaya sebagai hasil.
        logger.error(f"Calculation service returned non-JSON: {response.status_code}")
        raise EngineUnavailable(f"non-JSON response, HTTP {response.status_code}")
    return EngineResponse(status_code=response.status_code, body=body)



# Generic Class untuk menampung respoonse dari forwarder
class ForwarderResult(BaseModel):
    data: Any
    message: str | None = None
    success: bool

async def forward(path: str, payload: Union[BaseModel, dict]) -> ForwarderResult:
    url = f"{settings.calc_service_url}{path}"
    # print(url)
    logger.info(f"Forwarding to {url}")
    # print(payload.model_dump(), flush=True)

   # Handle both Pydantic model dan plain dict
    if isinstance(payload, BaseModel):
        json_payload = payload.model_dump()   # snake_case
    else:
        json_payload = payload                # sudah dict, langsung pakai

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=json_payload,            # pakai json_payload
                headers=get_internal_service_headers(),
                timeout=30.0
            )

            response.raise_for_status()
            result = response.json()
            # print(status == "status", result)

            unique_code = result.get("unique_code")
            success_message = get_message_by_unique_code(unique_code)

            return ForwarderResult(
                success = result.get("success", True),
                message = success_message,
                data = result.get("data"),
            )
        

    except httpx.HTTPStatusError as e:
        logger.error(f"Calculation service error: {e.response.status_code}")
        try:
            flask_response = e.response.json()
        except Exception:
            flask_response = {"detail": e.response.text}

        # Menggunakan HTTPExeption dari FastAPI, akan masuk kedalam detail
        # print(e.response)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=flask_response  # teruskan langsung, jangan replace
        )

        # Cukup menggunakan JSONResponse
        # return JSONResponse(
        #     status_code= e.response.status_code,
        #     content=flask_response
        # )


    except httpx.RequestError as e:
        logger.error(f"Cannot reach calculation service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calculation service unavailable"
        )