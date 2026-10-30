import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _configure_logging() -> logging.Logger:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root_logger.setLevel(level)

    return logging.getLogger("policypal.main")

from .api.routes import router
from .core.config import settings
from .core.database import init_db
from .core.embeddings import get_embeddings

logger = _configure_logging()

app = FastAPI(
    title="PolicyPal API",
    description="Multi-tenant RAG chatbot over HR and policy documents with conversation memory.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    logger.info("Starting PolicyPal API")
    init_db()         # create Neon tables if not exists
    get_embeddings()  # warm up BGE-small
    logger.info("PolicyPal startup completed")
