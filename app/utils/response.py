from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Any
from app.utils.base_schema import snake_to_camel

def to_camel_response(data: any) -> any:

    if hasattr(data, "model_dump"):
        data = data.model_dump()

    if isinstance(data, dict):
        return {
            snake_to_camel(key): to_camel_response(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [to_camel_response(item) for item in data]
    return data
 

def success_response(
    data: Any, 
    message: str | None = None, 
    success : bool = True,
    status_code: int = 200, 
    to_camel: bool = True  # Tambahkan flag ini
):
    
    # 1. Penanganan untuk Pydantic Model
    if isinstance(data, BaseModel) or hasattr(data, "model_dump"):
        # Jika to_camel=True, by_alias=True akan memanggil fungsi snake_to_camel
        # Jika to_camel=False, by_alias=False akan membiarkan attribute tetap snake_case
        formatted_data = data.model_dump(by_alias=to_camel)
        
    # 2. Penanganan untuk Dictionary/List mentah (misal hasil DB mentah)
    elif isinstance(data, (dict, list)):
        if to_camel:
            # Gunakan fungsi rekursif buatan Anda sebelumnya jika data bukan Pydantic
            formatted_data = to_camel_response(data) 
        else:
            # biarkan snake_case(database needs)
            formatted_data = data
    else:
        formatted_data = data

    # Kembalikan response sesuai standar SOP Gateway
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,  
            "data": formatted_data,
            "message": message
        }
    )



def to_json(model) -> dict | list:
    return jsonable_encoder(model, by_alias=True)
