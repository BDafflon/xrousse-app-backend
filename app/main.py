from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.db import get_session
from app.routers.auth import router as auth_router
from app.routers.drafts import router as drafts_router
from app.routers.events_backoffice import router as events_backoffice_router
from app.routers.events_me import router as events_me_router
from app.routers.events_public import router as events_public_router
from app.routers.moderation import router as moderation_router
from app.routers.rss import router as rss_router
from app.routers.saved_events import router as saved_events_router
from app.routers.subscriptions import router as subscriptions_router
from app.routers.tags import router as tags_router
from app.routers.uploads import router as uploads_router
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
    # Firefox's moz-extension:// origin is a random per-install UUID, not the
    # extension's stable manifest id (unlike Chrome's chrome-extension://,
    # which IS derived from the manifest's fixed `key` and is listed exactly
    # in cors_origins) — so the Firefox extension origin can only be matched
    # by scheme, not pinned to one exact origin. Scoped to the moz-extension
    # scheme only, not a broad wildcard.
    allow_origin_regex=r"moz-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(moderation_router)
app.include_router(events_backoffice_router)
app.include_router(events_me_router)
app.include_router(events_public_router)
app.include_router(drafts_router)
app.include_router(rss_router)
app.include_router(subscriptions_router)
app.include_router(saved_events_router)
app.include_router(users_router)
app.include_router(uploads_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
