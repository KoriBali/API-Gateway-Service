# Koribali API Gateway

[![Python Version](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Framework: FastAPI](https://img.shields.io/badge/Framework-FastAPI-0a9e9e)](https://fastapi.tiangolo.com/)
[![Architecture: Modular](https://img.shields.io/badge/Architecture-Modular-green)](#struktur-folder)

API Gateway untuk proyek **Koribali**. Berfungsi sebagai pintu masuk utama (single entry point) yang mengatur routing permintaan ke microservice kalkulasi, mengelola staging data proyek, serta menyediakan antarmuka yang konsisten untuk frontend dan sistem internal.

## Fitur Utama

* **API Routing & Orchestration:** Mengarahkan request ke Calculation Service dan mengelola response.
* **Staging Database:** Penyimpanan sementara hasil kalkulasi sebelum disimpan permanen.
* **Modular Feature Structure:** Setiap modul (Load Object, Opening Part, dll) memiliki router, schema, dan mapper sendiri.
* **Internal Maintenance:** Endpoint khusus untuk cleanup data staging via cron job.
* **Production Ready:** Dukungan CORS, logging, rate limiting (SlowAPI), dan deployment ke Railway.

## Tech Stacks

* **Language:** Python 3.12
* **Framework:** FastAPI
* **Database:** SQLAlchemy + SQLite (aiosqlite) untuk staging
* **Migrasi:** Alembic
* **Dependency Management:** Pipenv
* **Async HTTP Client:** HTTPX
* **Logging:** Loguru
* **Testing:** Pytest + Respx
* **Linter:** Ruff

## Struktur Folder

Proyek ini menggunakan **Modular/Feature-based Architecture**:

```text
koribali_api_gateway/
├── app/
│   ├── core/                   # Konfigurasi, database engine, logging, security
│   ├── database/               # Layer data (staging)
│   │   ├── models/             # SQLAlchemy models (identity, master, calculation, drawing, dll)
│   │   ├── mapper.py           # Mapping data generik
│   │   ├── orchestrator.py     # Orkestrasi penyimpanan staging
│   │   └── repository.py       # Query & persistence
│   ├── modules/                # Fitur-fitur utama (per domain)
│   │   ├── internal/           # Endpoint internal (cleanup, dll)
│   │   ├── load_object/        # Modul Load Object (router, schema, entity_mapper)
│   │   └── opening_part/       # Modul Opening Part
│   ├── services/               # Business logic & forwarding ke Calculation Service
│   ├── utils/                  # Helper functions (response, base_schema, dll)
│   └── main.py                 # Entry point aplikasi
├── alembic/                    # Migrasi database (Alembic)
├── tests/                      # Unit & integration test (Pytest + Respx)
├── .env.example
├── alembic.ini
├── Dockerfile                  # Container image
├── Pipfile / Pipfile.lock
├── Procfile                    # Untuk deployment Railway/Heroku
├── railway.json
└── README.md
```

## Instalasi & Persiapan

1. **Clone Repository:**
   ```bash
   git clone https://github.com/YantUgli/koribali_api_gateway.git
   cd koribali_api_gateway
   ```

2. **Install Dependencies:**
   ```bash
   pipenv install
   ```

3. **Aktifkan Virtual Environment:**
   ```bash
   pipenv shell
   ```

4. **Konfigurasi Environment:**
   ```bash
   cp .env.example .env
   ```
   Sesuaikan nilai di `.env` (terutama `CALC_SERVICE_URL` dan secret keys).

## Cara Menjalankan

**Development:**
```bash
uvicorn app.main:app --reload --port 9000
```

**Production (via Procfile):**
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## API Endpoints Utama

- `GET /` → Info API
- `GET /health` → Health check
- `POST /api/load-object/calculate` → Kalkulasi Load Object
- `POST /api/opening-part/calculate` → Kalkulasi Opening Part
- `DELETE /api/internal/cleanup-staging` → Cleanup staging (internal)

Dokumentasi lengkap Swagger UI tersedia di `/docs`.

## Testing & Quality Gate

```bash
# Jalankan test
pytest --cov=app tests/

# Linting
ruff check .
```

## Deployment

Proyek sudah siap deploy ke **Railway** (lihat `railway.json` dan `Procfile`), atau via container menggunakan `Dockerfile`.

