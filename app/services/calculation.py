import httpx
from pydantic import BaseModel
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, Any, Union
from loguru import logger

from app.core.config import settings
from app.core.security import get_internal_service_headers
from app.utils.message_response import get_message_by_unique_code 

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
                json=json_payload,            # ← pakai json_payload
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