from fastapi import APIRouter

from api.endpoints.chat import router as chat_router
from api.endpoints.models import router as models_router
from api.endpoints.monitoring import router as monitoring_router
from api.endpoints.testing import router as testing_router
from api.endpoints.validation import router as validation_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(models_router)
router.include_router(testing_router)
router.include_router(validation_router)
router.include_router(monitoring_router)
