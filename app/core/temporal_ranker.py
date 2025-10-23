# app/services/periodic_ranker.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any

from app.services.mongoDB_service import MongoService
from app.services.multi_job import ResumeRanker, MultiJobRankingService
from app.schemas import Resume, JobDescriptionTemplate

logger = logging.getLogger(__name__)


class PeriodicResumeRanker:
    """
    Background manager that runs MultiJobRankingService periodically between
    `start_hour_ist` (inclusive) and `end_hour_ist` (exclusive), in IST timezone.

    Usage:
        manager = PeriodicResumeRanker(...)
        manager.start()   # schedules background task
        ...
        await manager.stop()  # cancels and waits for clean shutdown
    """

    def __init__(
        self,
        *,
        interval_seconds: int = 3 * 60 * 60,  # 3 hours
        start_hour_ist: int = 6,
        end_hour_ist: int = 18,
        resume_ranker_factory: Optional[Callable[[], ResumeRanker]] = None,
        mongo_candidates_db: str = "algojobs",
        mongo_jobs_db: str = "algo-hr",
        top_k_per_job: int = 10,
    ):
        self.interval_seconds = int(interval_seconds)
        self.start_hour_ist = int(start_hour_ist)
        self.end_hour_ist = int(end_hour_ist)
        self.resume_ranker_factory = resume_ranker_factory or (lambda: ResumeRanker())
        self.mongo_candidates_db = mongo_candidates_db
        self.mongo_jobs_db = mongo_jobs_db
        self.top_k_per_job = int(top_k_per_job)

        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()

    async def _run_once(self) -> None:
        """
        One iteration: load resumes + job templates, run ranking, upsert.
        Runs synchronously (uses blocking code) but is executed inside async loop.
        """
        logger.info("PeriodicResumeRanker: starting ranking iteration")

        # create local ranker + services
        ranker = None
        svc_candidates = None
        svc_jobs = None
        try:
            ranker = self.resume_ranker_factory()

            svc_candidates = MongoService(db_name=self.mongo_candidates_db)
            raw_resumes = svc_candidates.get_all_resumes(limit=0)
            resumes = []
            for r in raw_resumes:
                try:
                    # try pydantic validation
                    if hasattr(Resume, "model_validate"):
                        resumes.append(Resume.model_validate(r))
                    else:
                        resumes.append(Resume.parse_obj(r))
                except Exception:
                    logger.exception("Skipping invalid resume doc: %s", r.get("_id") or r.get("id"))

            svc_jobs = MongoService(db_name=self.mongo_jobs_db)
            raw_jds = svc_jobs.get_all_jobdescriptions(limit=0)
            # normalize id presence if needed (safe)
            for d in raw_jds:
                if "_id" in d and "id" not in d:
                    d["id"] = d["_id"]

            job_templates = []
            for j in raw_jds:
                try:
                    if hasattr(JobDescriptionTemplate, "model_validate"):
                        job_templates.append(JobDescriptionTemplate.model_validate(j))
                    else:
                        job_templates.append(JobDescriptionTemplate.parse_obj(j))
                except Exception:
                    logger.exception("Skipping invalid job template doc: %s", j.get("_id") or j.get("id"))

            logger.info("Loaded %d resumes and %d job templates", len(resumes), len(job_templates))

            if not resumes or not job_templates:
                logger.warning("No resumes or job templates available — skipping this iteration")
                return

            msvc = MultiJobRankingService(mongo=svc_jobs, ranker=ranker, top_k_per_job=self.top_k_per_job)
            summary = msvc.rank_all_jobs_and_upsert(job_templates, candidate_filter=None, top_k_per_job=self.top_k_per_job)
            logger.info("Ranking iteration completed: %s", summary)

        except Exception:
            logger.exception("Error during ranking iteration")
        finally:
            # cleanup local resources
            try:
                if svc_candidates:
                    svc_candidates.close()
            except Exception:
                logger.exception("Error closing candidate MongoService")
            # Note: svc_jobs is passed into upsert service, which may keep client open;
            # close if we created it here
            try:
                if svc_jobs:
                    svc_jobs.close()
            except Exception:
                logger.exception("Error closing jobs MongoService")

    def _in_active_window(self) -> bool:
        """Return True if current IST hour is within configured active window."""
        now_utc = datetime.utcnow()
        ist_now = now_utc + timedelta(hours=5, minutes=30)
        return self.start_hour_ist <= ist_now.hour < self.end_hour_ist

    async def _loop(self) -> None:
        """Main background loop. Runs until stop() is called."""
        logger.info("PeriodicResumeRanker: background loop started")
        try:
            while not self._stopping.is_set():
                if self._in_active_window():
                    try:
                        # run blocking work in threadpool so event loop is not blocked
                        await asyncio.to_thread(self._run_once)
                    except Exception:
                        logger.exception("Unhandled exception while running ranking iteration")
                else:
                    logger.info("PeriodicResumeRanker: outside active window (%02d-%02d IST); skipping",
                                self.start_hour_ist, self.end_hour_ist)

                # wait for interval or until stopping
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    # timeout expired, continue next iteration
                    continue
        finally:
            logger.info("PeriodicResumeRanker: background loop stopped")

    def start(self) -> None:
        """Start the background task. Safe to call multiple times (idempotent)."""
        if self._task and not self._task.done():
            logger.debug("PeriodicResumeRanker already running")
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="periodic_resume_ranker")
        logger.info("PeriodicResumeRanker: task scheduled")

    async def stop(self, wait_timeout: float = 10.0) -> None:
        """Signal the loop to stop and wait for it to finish (with timeout)."""
        if not self._task:
            logger.debug("PeriodicResumeRanker not running")
            return
        logger.info("PeriodicResumeRanker: stopping background task")
        self._stopping.set()
        try:
            await asyncio.wait_for(self._task, timeout=wait_timeout)
        except asyncio.TimeoutError:
            logger.warning("PeriodicResumeRanker did not stop in time, cancelling task")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("PeriodicResumeRanker cancelled")
        finally:
            self._task = None
