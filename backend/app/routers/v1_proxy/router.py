"""Router assembly — mounts all v1 proxy endpoint routers."""

from fastapi import APIRouter

from .chat import router as chat_router
from .messages import router as messages_router
from .responses import router as responses_router
from .embeddings import router as embeddings_router
from .images import router as images_router
from .audio import router as audio_router
from .search import router as search_router
from .rerank import router as rerank_router
from .models import router as models_router
from .web import router as web_router

router = APIRouter(prefix="/v1", tags=["v1-proxy"])

# ── Mount all endpoint routers ──────────────────────────────────────────────
# Order matters: more specific paths must come before catch-all /models/{path}
router.include_router(chat_router)
router.include_router(messages_router)
router.include_router(responses_router)
router.include_router(embeddings_router)
router.include_router(images_router)
router.include_router(audio_router)
router.include_router(search_router)
router.include_router(rerank_router)
router.include_router(web_router)
router.include_router(models_router)  # last — has catch-all /models/{path}
