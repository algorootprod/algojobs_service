import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from sentence_transformers import SentenceTransformer
from app.core.config import config
from app import schemas
from app.services import ranking_service

logger = logging.getLogger(__name__)
router = APIRouter()

def get_model(request: Request) -> SentenceTransformer:
    """Dependency to get the loaded model from app state."""
    return request.app.state.model

@router.post("/rank", response_model=schemas.RankResponse)
def rank_resumes(
    req: schemas.RankRequest,
    model: SentenceTransformer = Depends(get_model)
):
    """
    Ranks a list of resumes against a job description.

    This endpoint accepts a job description and a list of structured resume objects.
    It uses a sentence-transformer model to compute the semantic similarity
    between the job description and each resume, returning a ranked list.
    """
    if not req.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is empty")

    n = len(req.resumes)
    if n == 0:
        raise HTTPException(status_code=400, detail="No resumes provided")
    if n > config.MAX_RESUMES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many resumes. Max allowed is {config.MAX_RESUMES}"
        )

    try:
        ranked_results = ranking_service.rank_resumes_by_similarity(
            model=model,
            job_description=req.job_description,
            resumes=req.resumes,
            batch_size=config.EMBED_BATCH_SIZE
        )
    except Exception as e:
        logger.exception("Failed during embedding or similarity calculation.")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

    # Apply top_k filter if provided
    top_k = req.top_k if req.top_k is not None else n
    results_to_return = ranked_results[:top_k]

    return schemas.RankResponse(
        total_resumes=n,
        returned=len(results_to_return),
        results=results_to_return
    )
