# 🚀 GitHub AI Engineer

An autonomous, repository-aware AI Code Intelligence platform that integrates AST structural parsing, change-aware Knowledge Graph analysis, Hybrid RAG (Dense Vector + BM25 Lexical + Graph Context), automated AI Code Reviews, Git Diff Intelligence, and GitHub PR Review analysis.

---

## 🏗 System Architecture

```
                               ┌──────────────────────────┐
                               │   Next.js 16 (React 19)  │
                               │   Tailwind CSS Frontend  │
                               └────────────┬─────────────┘
                                            │ HTTP / REST API
                               ┌────────────▼─────────────┐
                               │    FastAPI Backend API   │
                               └──────┬─────┬─────┬───────┘
                                      │     │     │
            ┌─────────────────────────┘     │     └────────────────────────┐
            ▼                               ▼                              ▼
┌───────────────────────┐       ┌───────────────────────┐      ┌───────────────────────┐
│  SQL Database         │       │  Qdrant Vector DB     │      │   GitHub REST API     │
│ (SQLite / Postgres)   │       │  (Local / Remote)     │      │   (api.github.com)    │
└───────────────────────┘       └───────────────────────┘      └───────────────────────┘
```

---

## 📋 Prerequisites

- **Python**: 3.10+ (Recommended: 3.11 / 3.13)
- **Node.js**: v18+ or v20+
- **Git**: Installed and available in PATH
- **Docker & Docker Compose** (Optional for containerized deployment)

---

## 🔑 Environment Configuration

Create `.env` files in `backend/` and `frontend/` using `.env.example` as a template.

### Key Environment Variables (`backend/.env`)

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `APP_NAME` | Name of the backend service | `GitHub AI Engineer API` |
| `DEBUG` | Enable debug mode (`true`/`false`) | `false` |
| `JWT_SECRET` | Production JWT secret key (must set in prod) | `your_production_jwt_secret_64_chars` |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | `http://localhost:3000,https://yourdomain.com` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./github_ai_engineer.db` or `postgresql://user:pass@host:5432/dbname` |
| `QDRANT_PATH` | Path for local Qdrant storage | `./qdrant_data` |
| `QDRANT_HOST` | Host for remote Qdrant instance | `qdrant` or `localhost` |
| `QDRANT_PORT` | Port for remote Qdrant | `6333` |
| `QDRANT_API_KEY` | API Key for Qdrant Cloud | `your_qdrant_api_key` |
| `OPENAI_API_KEY` | OpenAI API key for LLM inference | `sk-...` |
| `GITHUB_TOKEN` | GitHub Personal Access Token for PR access | `ghp_...` |
| `GITHUB_APP_ID` | GitHub App ID for authentication | `123456` |
| `GITHUB_APP_PRIVATE_KEY` | GitHub App RS256 private key | `-----BEGIN RSA PRIVATE KEY-----...` |
| `GITHUB_WEBHOOK_SECRET` | Secret key for HMAC SHA-256 signature verification | `your_webhook_secret` |
| `GITHUB_APP_INSTALLATION_ID` | Default installation ID | `12345678` |
| `GITHUB_PR_AUTOMATION_MODE` | Automation execution mode (`dry-run` / `disabled`) | `dry-run` |

### Frontend Variable (`frontend/.env`)

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Production backend REST API base URL | `http://localhost:8080/api` |

---

## 🤖 GitHub App & Webhook PR Automation

```
GitHub PR Event (opened/sync/reopen)
       │
       ▼
[POST /api/webhooks/github] ──► Verify HMAC SHA-256 Signature
       │
       ▼
[PRAutomationService] ────────► Idempotency & Action Check
       │
       ▼
[GitHubService] ──────────────► Fetch PR Metadata & Diff
       │
       ▼
[Diff + KG + RAG + AI Review] ─► Complete Intelligence Pipeline
       │
       ▼
[DRY-RUN Execution] ──────────► Log & Return Structured Summary (No auto-posting)
```

1. **Webhook Security**: Verifies `X-Hub-Signature-256` header using constant-time HMAC SHA-256 verification (`hmac.compare_digest`).
2. **Supported Events**: `pull_request` (actions: `opened`, `synchronize`, `reopened`).
3. **Dry-Run Mode**: Defaults to `GITHUB_PR_AUTOMATION_MODE=dry-run`. Executes complete PR intelligence analysis and logs output without automatically commenting on GitHub.
4. **Idempotency**: Prevents duplicate webhook deliveries using `WebhookEventLog` event tracking.


---

## ⚡ Quickstart — Local Setup

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend dev server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Backend API will be accessible at:
- **API Base**: `http://localhost:8080/api`
- **Swagger Docs**: `http://localhost:8080/docs`
- **Health Check**: `http://localhost:8080/health`

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

Frontend app will be accessible at `http://localhost:3000`.

---

## 🐳 Docker Deployment

Run the entire application stack (Backend, Frontend, and Qdrant Vector DB) with Docker Compose:

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down
```

Services in Docker Compose:
- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8080`
- **Qdrant Vector DB**: `http://localhost:6333`

---

## 🧪 Verification & Testing

### Backend Unit & Integration Tests

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/test_backend.py tests/test_github_service.py
```

### Frontend Typecheck & Build

```bash
cd frontend
npx tsc --noEmit
npm run build
```

---

## 🛡 Security & Production Readiness

1. **Secrets Management**: No API keys or tokens are stored in source code. All secrets are injected strictly via environment configuration.
2. **SSRF & Input Sanitation**: GitHub repository URLs and revision identifiers undergo strict character validation before processing.
3. **Database Scalability**: Easily switches from SQLite to PostgreSQL by updating `DATABASE_URL`.
4. **Vector Storage**: Supports local storage or cloud-hosted Qdrant cluster through `QDRANT_HOST` and `QDRANT_API_KEY`.
5. **CORS Control**: Dynamic origin authorization managed via `CORS_ORIGINS`.