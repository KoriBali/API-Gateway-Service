import mimetypes

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.modules.files.storage import LocalStorage, StorageError, get_storage

# Pengganti signed URL Supabase untuk backend local. Tanpa token login, sama seperti
# signed URL: yang menjaga akses adalah tanda tangan dan batas waktunya.
routerLocalStorage = APIRouter(prefix="/api/storage/local", tags=["Request Files"], include_in_schema=False)



@routerLocalStorage.get("/{path:path}")
async def download_local_object(
    path: str,
    name: str = Query(...),
    expires: int = Query(...),
    signature: str = Query(...),
):
    backend = get_storage()
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    # Route ini mati di backend supabase.
    if not isinstance(backend, LocalStorage) or not backend.verify(path, name, expires, signature):
        raise not_found
    try:
        target = backend.file_path(path)
    except StorageError:
        raise not_found
    if not target.is_file():
        raise not_found
    return FileResponse(
        target,
        filename=name,
        media_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
    )
