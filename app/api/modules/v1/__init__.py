"""V1 API Router - aggregates all v1 endpoints."""

from fastapi import APIRouter

from .profiles.router import router as profiles_router
from .photos.router import router as photos_router
from .discovery.router import router as discovery_router
from .matches.router import router as matches_router
from .feedback.router import router as feedback_router
from .chat.router import router as chat_router
from .privacy.router import router as privacy_router
from .safety.router import router as safety_router
from .subscriptions.router import subscription_router

router = APIRouter(prefix="/v1")

# Include sub-routers
router.include_router(profiles_router)
router.include_router(photos_router)
router.include_router(discovery_router)
router.include_router(matches_router)
router.include_router(feedback_router)
router.include_router(chat_router)
router.include_router(privacy_router)
router.include_router(safety_router)
router.include_router(subscription_router)

