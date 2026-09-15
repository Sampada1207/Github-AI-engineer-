from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routes import auth_router, projects_router, repos_router, chat_router, ai_router, webhooks_router
import app.models.models  # noqa: F401 — register ORM models

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for AI-powered code intelligence platform.",
    version="1.0.0",
    debug=settings.DEBUG
)

cors_origins = settings.cors_origin_list()
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(repos_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router)


@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "message": "Welcome to GitHub AI Engineer API portal. Access documentation at /docs"
    }

@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    db_status = "ok"
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "app_name": settings.APP_NAME,
        "database": db_status,
        "environment": "development" if settings.DEBUG else "production"
    }

