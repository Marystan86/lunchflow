from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.badges import router as badges_router
from backend.app.api.routes.events import router as events_router
from backend.app.api.routes.lightning import router as lightning_router
from backend.app.api.routes.meeting_requests import router as meeting_requests_router
from backend.app.api.routes.me import router as me_router
from backend.app.api.routes.members import router as members_router
from backend.app.api.routes.news import router as news_router
from backend.app.api.routes.store import router as store_router
from backend.app.api.routes.dev import router as dev_router
from backend.app.api.routes.users import router as users_router

__all__ = ["api_router"]

from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(me_router, tags=["me"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(members_router, tags=["members"])
api_router.include_router(badges_router, tags=["badges"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(news_router, tags=["news"])
api_router.include_router(store_router, tags=["store"])
api_router.include_router(lightning_router, tags=["lightning"])
api_router.include_router(meeting_requests_router, tags=["meeting_requests"])
api_router.include_router(dev_router, tags=["dev"])
