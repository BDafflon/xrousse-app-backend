from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.drafts import router as drafts_router
from app.routers.events_backoffice import router as events_backoffice_router
from app.routers.events_public import router as events_public_router
from app.routers.rss import router as rss_router
from app.routers.tags import router as tags_router

app = FastAPI()

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


@app.get("/health")
def health_check():
    return {"status": "ok"}
