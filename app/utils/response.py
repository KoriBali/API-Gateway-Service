from typing import Any

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(
    data: Any, 
    message: str | None = None, 
    success : bool = True,
    status_code: int = 200, 
    to_camel: bool = True  # Tambahkan flag ini
) -> JSONResponse:
    
   
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,  
            "data": jsonable_encoder(data, by_alias=to_camel),
            "message": message
        }
    )


