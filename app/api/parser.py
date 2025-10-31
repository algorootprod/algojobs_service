import asyncio
import uuid
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
import tempfile
import shutil
from typing import List
import random
from fastapi import Query
from app.services.resume_parser import ResumeProcessor
import logging

router = APIRouter()
logger = logging.getLogger("resume_async")
logger.setLevel(logging.INFO)

#  FastAPI endpoint
@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...), owner_id: str = "60c72b2f5f1b2c001f0a1234",api_key:str=None):
    """
    Upload a resume file (multipart/form-data). The file is temporarily saved on disk,
    processed asynchronously (GenAI + Mongo), then deleted.
    - owner_id: optional owner id for upsert (defaults to dummy ID; replace in real use)
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: GOOGLE_API_KEY not set",
        )

    # Save uploaded file to temp path
    suffix = os.path.splitext(file.filename)[1] or ".pdf"
    tmp_name = f"{uuid.uuid4().hex}{suffix}"
    tmp_path = os.path.join("/tmp", tmp_name) if os.name != "nt" else os.path.join(os.getenv("TEMP", "."), tmp_name)

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.exception("Failed to save uploaded file: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    processor = ResumeProcessor(api_key=api_key)

    prompt = "Parse this document and extract the resume information according to the provided schema."

    try:
        result = await processor.process_resume_file(local_path=tmp_path, owner_id=owner_id, prompt=prompt)

        # Optionally return compact response
        return JSONResponse(status_code=200, content={
            "status": "ok",
            "uploaded_filename": result.get("uploaded_doc"),
            "candidate_phone": result.get("candidate_phone"),
            "db_saved": result.get("db_saved"),
            "db_doc_id": str(result.get("db_doc").get("_id")) if result.get("db_doc") and result.get("db_doc").get("_id") else None
        })
    except Exception as exc:
        logger.exception("Processing failed: %s", exc)
        # Provide helpful error classification to clients
        if "model is overloaded" in str(exc).lower() or "503" in str(exc).lower() or "unavailable" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Upstream model unavailable. Please retry later.")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(exc)}")
    finally:
        # always try to clean up temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            logger.warning("Failed to remove temp file %s", tmp_path)


# Bulk endpoint
@router.post("/upload-resumes-bulk")
async def upload_resumes_bulk(
    files: List[UploadFile] = File(...),
    owner_id: str = "60c72b2f5f1b2c001f0a1234",
    retry_attempts: int = Query(3, ge=1, le=10),
    concurrency: int = Query(4, ge=1, le=20),
    api_key: str = None
):
    """
    Bulk parse resumes.
    - files: multipart upload (multiple files).
    - owner_id: owner id for DB upsert (replace in production with authenticated user id).
    - retry_attempts: number of attempts per file (default 3).
    - concurrency: max concurrent processing tasks (default 4).
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: GOOGLE_API_KEY not set",
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # create processor once and reuse client connections
    processor = ResumeProcessor(api_key=api_key)

    sem = asyncio.Semaphore(concurrency)

    # ensure a working temp dir for all files (will be cleaned up)
    tmp_dir = tempfile.mkdtemp(prefix="resume_bulk_")

    async def _save_upload_to_temp(upload: UploadFile) -> str:
        """Save UploadFile to a temp path and return the path."""
        suffix = os.path.splitext(upload.filename)[1] or ".pdf"
        tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{suffix}")
        try:
            with open(tmp_path, "wb") as f:
                content = await upload.read()
                f.write(content)
        except Exception as e:
            logger.exception("Failed saving upload %s: %s", upload.filename, e)
            raise
        return tmp_path

    async def _process_with_attempts(local_path: str, original_filename: str):
        """
        Tries to process the file up to `retry_attempts`. Returns a dict result.
        Retries are for the full pipeline (upload -> generate -> validate -> db).
        """
        last_error = None
        for attempt in range(1, retry_attempts + 1):
            try:
                # Use semaphore to bound concurrent access to model & DB
                async with sem:
                    result = await processor.process_resume_file(
                        local_path=local_path,
                        owner_id=owner_id,
                        prompt="Parse this document and extract the resume information according to the provided schema."
                    )
                # success
                return {
                    "filename": original_filename,
                    "success": True,
                    "attempts": attempt,
                    "candidate_phone": result.get("candidate_phone"),
                    "db_doc_id": str(result.get("db_doc").get("_id")) if result.get("db_doc") and result.get("db_doc").get("_id") else None,
                }
            except Exception as exc:
                last_error = exc
                # detect transient vs permanent via message heuristics
                msg = str(exc).lower()
                is_transient = any(token in msg for token in ("503", "model is overloaded", "unavailable", "timeout"))

                logger.warning("File %s attempt %d/%d failed (transient=%s): %s",
                               original_filename, attempt, retry_attempts, is_transient, exc)

                if attempt >= retry_attempts:
                    # final failure
                    return {
                        "filename": original_filename,
                        "success": False,
                        "attempts": attempt,
                        "error": str(last_error),
                    }

                # backoff before next attempt (exponential + jitter)
                backoff = min(2 ** (attempt - 1), 8)
                jitter = random.uniform(0, backoff * 0.25)
                sleep_for = backoff + jitter
                logger.info("Sleeping %.2fs before retrying file %s (attempt %d)", sleep_for, original_filename, attempt + 1)
                await asyncio.sleep(sleep_for)

        # should not reach here, but return failure defensively
        return {
            "filename": original_filename,
            "success": False,
            "attempts": retry_attempts,
            "error": str(last_error) if last_error else "Unknown error",
        }

    # prepare all files: save to disk
    save_tasks = []
    for upload in files:
        save_tasks.append(_save_upload_to_temp(upload))

    try:
        saved_paths = await asyncio.gather(*save_tasks)
    except Exception as e:
        # cleanup and fail fast
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.exception("Failed saving uploaded files: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed saving uploaded files: {e}")

    # spawn processing coroutines for each saved file
    processing_coros = []
    for upload, path in zip(files, saved_paths):
        processing_coros.append(_process_with_attempts(local_path=path, original_filename=upload.filename))

    # Run them concurrently (bounded by semaphore)
    results = await asyncio.gather(*processing_coros)

    # cleanup temp dir
    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        logger.warning("Failed to remove temp dir %s", tmp_dir)

    # build summary
    success_count = sum(1 for r in results if r.get("success"))
    failure_count = len(results) - success_count

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "total": len(results),
            "success": success_count,
            "failed": failure_count,
            "retry_attempts_per_task": retry_attempts,
            "results": results,
        },
    )
