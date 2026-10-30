from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.db import get_session
from app.routers.auth import router as auth_router
from app.routers.drafts import router as drafts_router
from app.routers.events_backoffice import router as events_backoffice_router
from app.routers.events_public import router as events_public_router
from app.routers.rss import router as rss_router
from app.routers.subscriptions import router as subscriptions_router
from app.routers.tags import router as tags_router
from app.routers.users import router as users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Opt-in, idempotent first-admin bootstrap — see app/bootstrap.py and the
    # admin_email/admin_password settings in app/config.py. Goes through the
    # get_session dependency override (not a module-level engine) so tests
    # can exercise this against the in-memory test session like any route.
    session_override = app.dependency_overrides.get(get_session, get_session)
    result = session_override()
    if hasattr(result, "__next__"):
        session = next(result)
        try:
            bootstrap_admin(session)
        finally:
            result.close()
    else:
        bootstrap_admin(result)
    yield


app = FastAPI(lifespan=lifespan)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(events_backoffice_router)
app.include_router(events_public_router)
app.include_router(drafts_router)
app.include_router(rss_router)
app.include_router(subscriptions_router)
app.include_router(users_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
