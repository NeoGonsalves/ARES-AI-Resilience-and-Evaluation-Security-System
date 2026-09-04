# ARES API

FastAPI/PostgreSQL foundation for ARES. It owns organizations, users, projects, policies, controlled test runs, findings, and redacted evidence metadata.

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:EXECUTION_PAYLOAD_ENCRYPTION_KEY = (& .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
$env:OPENAI_API_KEY = "set-your-server-side-key"
$env:DATABASE_URL = "postgresql+psycopg://ares:ares@localhost:5432/ares"
uvicorn app.main:app --reload --port 8000
```

For the full local stack, from the repository root run:

```powershell
docker compose --env-file backend/.env up --build
```

The development identity is `developer@local` by default. Set `ALLOW_DEV_IDENTITY=false` before deployment; a real OIDC/JWT verifier must then provide the caller identity. API documentation is available at `http://localhost:8000/docs`.

## Data and safety boundary

- Raw system prompts and user prompts are stored only as a short-lived, encrypted execution payload, then deleted when the run completes, fails, or is cancelled. Ordinary records retain only allow-listed metadata and a keyed fingerprint.
- Raw model output is analysed in memory and is never stored by this foundation.
- Provider credentials are not represented in API requests or database records.
- A background worker processes `queued` jobs. OpenAI is the first supported provider and uses the Responses API with `store=false`; add `OPENAI_API_KEY` and a Fernet `EXECUTION_PAYLOAD_ENCRYPTION_KEY` only to the server environment.

## Migrations

Development auto-creates the schema. In deployed environments set `AUTO_CREATE_SCHEMA=false` and run:

```powershell
alembic upgrade head
```
