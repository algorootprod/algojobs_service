import logging
import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from app.core.config import config
from app import ranker, scheduler
from app.services import agent_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan for startup and shutdown tasks.
    This replaces on_event("startup") / on_event("shutdown").
    """
    # STARTUP
    logger.info("Application startup (lifespan)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading embedding model '{config.EMBEDDING_MODEL}' on device '{device}'")
    # This is a blocking call but acceptable here; if you expect very long init times,
    # consider running it in a thread executor.
    app.state.model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
    logger.info("Embedding model loaded successfully.")

    try:
        yield
    finally:
        # SHUTDOWN
        logger.info("Application shutdown (lifespan)...")
        # Release model reference (allow GC); if model has explicit close/free methods, call them here.
        app.state.model = None

        # Ensure agent_registry cleans up running agents
        try:
            await agent_registry.shutdown()
        except Exception:
            logger.exception("Error while shutting down agent registry")

# Create FastAPI app with lifespan
app = FastAPI(
    title="AI HR Service",
    description="An API for ranking resumes and scheduling candidate interviews.",
    version="1.0.0",
    lifespan=lifespan
)

# --- API Routers ---
app.include_router(ranker, prefix=config.API_V1_STR, tags=["Resume Ranker"])
app.include_router(scheduler, prefix=config.API_V1_STR, tags=["Interview Scheduler"])
