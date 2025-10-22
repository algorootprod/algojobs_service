import logging
import torch
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from app.core.config import config
from app import ranker, scheduler
from app.services import agent_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Intelligent HR Service",
    description="An API for ranking resumes and scheduling candidate interviews.",
    version="1.0.0"
)

# --- Event Handlers ---
@app.on_event("startup")
def startup_event():
    """
    Application startup event.
    Loads the sentence transformer model into the app's state.
    """
    logger.info("Application startup...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading embedding model '{config.EMBEDDING_MODEL}' on device '{device}'")
    
    # Store the model in the app state for access in endpoints
    app.state.model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
    logger.info("Embedding model loaded successfully.")

@app.on_event("shutdown")
def shutdown_event():
    """
    Application shutdown event.
    """
    logger.info("Application shutdown.")
    # You can add cleanup logic here if needed, like releasing model resources
    app.state.model = None

# --- API Routers ---
app.include_router(ranker, prefix=config.API_V1_STR, tags=["Resume Ranker"])
app.include_router(scheduler, prefix=config.API_V1_STR, tags=["Interview Scheduler"])

# TODO
# @app.on_event("shutdown")
# async def stop_all_agents():
#     for agent_name in list(agent_registry._registry.keys()):
#         await agent_registry.stop_agent(agent_name)
