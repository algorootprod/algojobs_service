import asyncio
import logging
import random
from typing import Optional, Any, Dict
import google.genai as genai
from app.schemas import CandidateResume
from app.services.mongoDB_service import MongoService

logger = logging.getLogger("Resume Parser")
logger.setLevel(logging.INFO)


class ResumeProcessor:
    """
    Async wrapper around the (blocking) genai client + MongoService calls.
    Uses asyncio.to_thread to avoid blocking the event loop.
    Implements retry logic for transient GenAI errors (503 / model overloaded).
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        max_retries: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 16.0,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff

    async def _run_with_retries(self, func, *args, **kwargs):
        """Generic retry loop for functions that may raise transient errors."""
        attempt = 0
        while True:
            try:
                # Run blocking function in thread
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as exc:
                attempt += 1
                msg = str(exc).lower()
                is_transient = False

                # heuristics to detect transient GenAI/unavailable errors
                if "503" in msg or "unavailable" in msg or "model is overloaded" in msg or "model overloaded" in msg:
                    is_transient = True

                if not is_transient or attempt > self.max_retries:
                    logger.exception("Non-retriable error or max retries exceeded")
                    raise

                # exponential backoff with jitter
                backoff = min(self.base_backoff * (2 ** (attempt - 1)), self.max_backoff)
                jitter = random.uniform(0, backoff * 0.2)
                sleep_for = backoff + jitter
                logger.warning(
                    "Transient error detected (attempt %d/%d). Sleeping %.2fs before retrying. Error: %s",
                    attempt,
                    self.max_retries,
                    sleep_for,
                    exc,
                )
                await asyncio.sleep(sleep_for)

    async def upload_file(self, local_path: str) -> Any:
        """Upload file via genai client (blocking) with retry logic."""
        def _upload():
            # client's upload is blocking in your example
            return self.client.files.upload(file=local_path)

        return await self._run_with_retries(_upload)

    async def generate_resume_json(self, uploaded_doc: Any, prompt: str) -> Dict:
        """Call generate_content (blocking) with retry logic and return parsed JSON dict."""
        def _generate():
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[uploaded_doc, prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": CandidateResume,
                },
            )
            # the API in your example holds JSON text at response.text
            return response.text

        raw_text = await self._run_with_retries(_generate)

        # Validate JSON string -> CandidateResume model (blocking)
        def _validate(text: str):
            # You used model_validate_json in your snippet
            return CandidateResume.model_validate_json(text)

        resume_model = await asyncio.to_thread(_validate, raw_text)
        return resume_model

    async def upsert_to_db(self, owner_id: str, parsed_resume: CandidateResume) -> Optional[Dict]:
        """Upsert resume into MongoDB using your MongoService (runs blocking)."""
        def _upsert():
            mongo = MongoService()
            try:
                saved = mongo.upsert_resume(owner_id=owner_id, parsed_data=parsed_resume)
                return saved
            finally:
                mongo.close()

        return await asyncio.to_thread(_upsert)

    async def process_resume_file(self, local_path: str, owner_id: str, prompt: str) -> Dict:
        """Full pipeline: upload -> generate -> validate -> store. Returns DB doc (or raises)."""
        uploaded_doc = await self.upload_file(local_path)
        resume_model = await self.generate_resume_json(uploaded_doc, prompt)
        saved_doc = await self.upsert_to_db(owner_id=owner_id, parsed_resume=resume_model)
        return {
            "uploaded_doc": getattr(uploaded_doc, "name", None),
            "candidate_phone": getattr(resume_model, "phone", None),
            "db_saved": bool(saved_doc),
            "db_doc": saved_doc,
        }
