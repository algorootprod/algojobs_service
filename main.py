import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from app import ranker, scheduler, config, MongoService, AgentRegistry, PeriodicResumeRanker

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
    # device = "cuda" if torch.cuda.is_available() else "cpu"
    device = "cpu"
    logger.info(f"Loading embedding model '{config.EMBEDDING_MODEL}' on device '{device}'")
    app.state.model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
    logger.info("Embedding model loaded successfully.")

    app.state.mongo_service = MongoService(db_name="algo-hr")
    logger.info("MongoDB service initialized.")

    app.state.agent_registry=AgentRegistry(30)
    logger.info("Agent registry initialized.")

    app.state.periodic_ranker = PeriodicResumeRanker(
        interval_seconds=3 * 60 * 60,
        start_hour_ist=9,
        end_hour_ist=18,
    )
    app.state.periodic_ranker.start()

    try:
        yield
    finally:
        # SHUTDOWN
        logger.info("Application shutdown (lifespan)...")
        app.state.model = None
        try:
            await app.state.periodic_ranker.stop()
        except Exception:
            logger.exception("Error stopping periodic ranker")
        try:
            await app.state.agent_registry.shutdown()
        except Exception:
            logger.exception("Error while shutting down agent registry")
        try:
            app.state.mongo_service.close()
        except Exception:
            logger.exception("Error while shutting down mongo service")

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

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000,
        reload=True
        )