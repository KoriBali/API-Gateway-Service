from typing import Any

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.utils.base_schema import snake_to_camel


def _camelize_keys(obj: Any) -> Any:
    """
    Recursively convert dict keys ke camelCase.

    jsonable_encoder(by_alias=True) hanya meng-camelCase-kan nama *field*
    dari model Pydantic (lewat alias). Key dict biasa (mis. envelope manual
    seperti {"external_objects": [...]}) tidak ikut berubah, sehingga output
    jadi campur snake_case + camelCase. Fungsi ini menyeragamkan sisa key dict.

    Idempoten: key yang sudah camelCase / satu kata tidak berubah.
    """
    if isinstance(obj, dict):
        return {
            (snake_to_camel(k) if isinstance(k, str) else k): _camelize_keys(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_camelize_keys(item) for item in obj]
    return obj


def success_response(
    data: Any,
    message: str | None = None,
    success : bool = True,
    status_code: int = 200,
    to_camel: bool = True  # Tambahkan flag ini
) -> JSONResponse:

    encoded = jsonable_encoder(data, by_alias=to_camel)
    if to_camel:
        encoded = _camelize_keys(encoded)

    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "data": encoded,
            "message": message
        }
    )
