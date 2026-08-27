from pydantic_settings import BaseSettings, SettingsConfigDict
import ssl
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


class Settings(BaseSettings):
    app_name: str = "API Gateway"
    app_port: int = 8000

    calc_service_url: str
    calc_service_key: str

    DATABASE_URL: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

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


    model_config = SettingsConfigDict(env_file=".env", extra="ignore")



def build_async_db_url_and_connect_args(raw_url: str) -> tuple[str, dict]:
    """
    Normalisasi DATABASE_URL agar kompatibel dengan asyncpg + provider SSL
    seperti Neon/Supabase.
    - Pastikan skema 'postgresql+asyncpg://'
    - Buang query param yang tidak dipahami asyncpg (sslmode, channel_binding)
    - Sisipkan SSLContext lewat connect_args bila SSL diminta
    """
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
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    clean_url = urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return clean_url, connect_args



settings = Settings()