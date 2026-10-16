"""Penyimpanan fisik berkas request (V2). Dua backend, dipilih lewat STORAGE_BACKEND:
supabase untuk cloud, local untuk dev dan skrip regresi (tanpa kredensial).

Kode lain hanya memanggil get_storage(), store_upload(), dan discard(). Tidak ada kode
lain yang tahu backend mana yang aktif. Kolom storage_ref berisi path objek yang sama
untuk kedua backend."""
import hashlib
import hmac
import time
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException, UploadFile, status
from loguru import logger

from app.core.config import settings



class StorageError(Exception):
    """Backend storage menolak atau tidak bisa dihubungi."""



def new_object_path(request_id: str) -> str:
    """Path objek baru. Tanpa nama file: nama tampilan hidup di request_files.file_name,
    dan nama ketikan worker bisa berisi karakter yang tidak aman untuk path."""
    return f"requests/{request_id}/{uuid.uuid4()}"



# ===== Supabase Storage =====
class SupabaseStorage:
    """Storage REST API lewat httpx. Bucket private: berkas hanya bisa diunduh lewat signed URL."""

    def __init__(self, url: str, key: str, bucket: str):
        self._base = f"{url.rstrip('/')}/storage/v1"
        self._bucket = bucket
        self._headers = {"apikey": key}
        # service_role lama berbentuk JWT dan dikirim juga sebagai Bearer.
        # Secret key baru (sb_secret_...) bukan JWT, cukup lewat header apikey.
        if key.startswith("eyJ"):
            self._headers["Authorization"] = f"Bearer {key}"

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise StorageError(f"Supabase Storage unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise StorageError(f"Supabase Storage {method} {response.status_code}: {response.text[:300]}")
        return response

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        await self._request(
            "POST", f"{self._base}/object/{self._bucket}/{path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "false"},
        )

    async def signed_url(self, path: str, *, file_name: str, expires_in: int) -> str:
        response = await self._request(
            "POST", f"{self._base}/object/sign/{self._bucket}/{path}", json={"expiresIn": expires_in},
        )
        # signedURL relatif ke /storage/v1: "/object/sign/<bucket>/<path>?token=..."
        signed = response.json()["signedURL"]
        # download=<nama> membuat Supabase mengirim Content-Disposition dengan nama ini.
        return f"{self._base}{signed}&{urlencode({'download': file_name}, quote_via=quote)}"

    async def remove(self, paths: list[str]) -> None:
        if paths:
            await self._request("DELETE", f"{self._base}/object/{self._bucket}", json={"prefixes": paths})



# ===== Disk lokal =====
class LocalStorage:
    """Meniru bucket private: berkas di folder lokal, diunduh lewat URL bertanda tangan HMAC
    yang dilayani GET /api/storage/local/{path}. Bentuk kontrak unduh sama dengan Supabase."""

    def __init__(self, root: str, base_url: str, secret: str):
        self._root = Path(root).resolve()
        self._base_url = base_url.rstrip("/")
        self._secret = secret.encode()

    def file_path(self, path: str) -> Path:
        target = (self._root / path).resolve()
        # Tanda tangan sudah menjaga path, ini lapis kedua terhadap "../".
        if not target.is_relative_to(self._root):
            raise StorageError("Path escapes the storage root")
        return target

    def _signature(self, path: str, file_name: str, expires: int) -> str:
        message = f"{path}\n{file_name}\n{expires}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def verify(self, path: str, file_name: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        return hmac.compare_digest(self._signature(path, file_name, expires), signature)

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        target = self.file_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def signed_url(self, path: str, *, file_name: str, expires_in: int) -> str:
        expires = int(time.time()) + expires_in
        query = urlencode({
            "name": file_name,
            "expires": expires,
            "signature": self._signature(path, file_name, expires),
        }, quote_via=quote)
        return f"{self._base_url}/api/storage/local/{quote(path)}?{query}"

    async def remove(self, paths: list[str]) -> None:
        for path in paths:
            self.file_path(path).unlink(missing_ok=True)



@lru_cache
def get_storage() -> SupabaseStorage | LocalStorage:
    if settings.STORAGE_BACKEND == "supabase":
        return SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY, settings.STORAGE_BUCKET)
    return LocalStorage(settings.STORAGE_LOCAL_DIR, settings.STORAGE_LOCAL_BASE_URL, settings.JWT_SECRET)



# ===== Helper untuk router =====
async def read_upload(upload: UploadFile) -> bytes:
    """Isi berkas unggahan. 413 bila melebihi FILE_MAX_BYTES, 422 bila kosong."""
    data = await upload.read(settings.FILE_MAX_BYTES + 1)
    if len(data) > settings.FILE_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.FILE_MAX_BYTES} byte limit",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="file is empty")
    return data


async def store_upload(request_id: str, upload: UploadFile) -> str:
    """Simpan berkas unggahan ke storage dan kembalikan path objeknya (storage_ref).
    Dipanggil SEBELUM baris DB ditulis; bila penulisan DB gagal, pemanggil memanggil discard."""
    data = await read_upload(upload)
    path = new_object_path(request_id)
    try:
        await get_storage().put(path, data, upload.content_type or "application/octet-stream")
    except StorageError as exc:
        logger.error(f"Storage put failed for {path}: {exc}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="File storage is unavailable") from exc
    return path


async def discard(paths) -> None:
    """Hapus objek yang barisnya sudah tidak ada (atau tidak jadi ditulis). Best effort:
    kegagalan hanya dicatat, karena baris DB sudah final dan objek yatim tidak merusak data."""
    unique = sorted({p for p in paths if p})
    if not unique:
        return
    try:
        await get_storage().remove(unique)
    except StorageError as exc:
        logger.warning(f"Storage cleanup failed for {len(unique)} object(s): {exc}")


async def download_url(storage_ref: str, file_name: str) -> str:
    try:
        return await get_storage().signed_url(
            storage_ref, file_name=file_name, expires_in=settings.FILE_DOWNLOAD_URL_SECONDS,
        )
    except StorageError as exc:
        logger.error(f"Storage sign failed for {storage_ref}: {exc}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="File storage is unavailable") from exc