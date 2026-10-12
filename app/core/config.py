from pydantic_settings import BaseSettings, SettingsConfigDict
import ssl
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import os

class Settings(BaseSettings):
    app_name: str = "API Gateway"
    app_port: int = 8000

    calc_service_url: str
    calc_service_key: str

    """
    ===== Calculation stub =====
        True  = endpoint /api/calculate mengembalikan hasil placeholder (calc-service belum siap). 
        False = teruskan ke calc-service via forward().
        Flip ke False (atau set CALC_STUB_MODE=false di .env) saat calc-service siap.
    """
    calc_stub_mode: bool = True
    

    DATABASE_URL: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # ===== Database TLS =====
    # Path CA cert untuk verifikasi server DB (Supabase). Relatif ke root project.
    DB_SSL_CA_PATH: str = "certs/prod-ca-2021.crt"
    DB_SSL_CHECK_HOSTNAME: bool = True
    # Verifikasi CA. Set False HANYA bila CA bermasalah di runtime (mis. OpenSSL
    # ketat menolak cert Supabase 2021: "CA cert does not include key usage
    # extension"). False = koneksi TETAP terenkripsi tapi TIDAK terverifikasi
    # (setara perilaku lama CERT_NONE) — utang teknis, tutup dengan CA valid.
    DB_SSL_VERIFY: bool = True

    DEBUG: str
    INTERNAL_CLEANUP_TOKEN: str

    # ===== JWT / Auth =====
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ===== Seed Superadmin =====
    SEED_SUPERADMIN_USERNAME: str = "superadmin"
    SEED_SUPERADMIN_EMAIL: str = "superadmin@example.com"
    SEED_SUPERADMIN_PASSWORD: str
    SEED_SUPERADMIN_FULL_NAME: str = "Super Admin"

    # ===== Seed Employee =====
    SEED_DEFAULT_USER_PASSWORD: str = "password"

    # ===== CORS =====
    # Daftar origin dipisah koma. Default dev;
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]



    model_config = SettingsConfigDict(env_file=".env", extra="ignore")



def build_async_db_url_and_connect_args(
    raw_url: str,
    ca_path: str | None = None,
    check_hostname: bool = True,
    verify: bool = True,
) -> tuple[str, dict]:
    parts = urlsplit(raw_url)

    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme.startswith("postgresql+") and "asyncpg" not in scheme:
        scheme = "postgresql+asyncpg"

    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)  # asyncpg tidak mengerti ini

    connect_args: dict = {}
    if sslmode not in ("disable", "allow"):
        if verify:
            # Verifikasi server DB terhadap CA yang di-pin (bukan CERT_NONE).
            if ca_path and os.path.exists(ca_path):
                ssl_ctx = ssl.create_default_context(cafile=ca_path)
            else:
                # Fallback: CA bawaan sistem (tetap terverifikasi, bukan CERT_NONE).
                ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = check_hostname
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            # Fallback darurat: terenkripsi tapi TIDAK terverifikasi.
            # Dipakai bila CA runtime bermasalah (OpenSSL ketat menolak cert Supabase).
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    clean_url = urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return clean_url, connect_args




settings = Settings()