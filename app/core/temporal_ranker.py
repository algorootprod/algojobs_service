import asyncio
import logging
import contextlib
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, List

from app.services.mongoDB_service import MongoService
from app.services.multi_job import MultiJobRankingService
from app.services.ranking_service import ResumeRanker
from app.schemas import Job

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PeriodicResumeRanker:
    """
    Lightweight periodic runner that mirrors your __main__ test but runs continuously.

    Initialization parameters (only these three are accepted):
      - interval_seconds: how often to run (default 3 hours)
      - start_hour_ist: inclusive start hour in IST for allowed runs
      - end_hour_ist: exclusive end hour in IST for allowed runs

    Behavior:
      - Uses MongoService(db_name="algojobs") to fetch jobs and to create MultiJobRankingService.
      - Validates jobs using the single Job schema; uses raw dict fallback if validation fails.
      - Each run executes the same logic as your __main__ snippet.
    """

    def __init__(
        self,
        *,
        interval_seconds: int = 3 * 60 * 60,
        start_hour_ist: int = 6,
        end_hour_ist: int = 18,
    ):
        self.interval_seconds = int(interval_seconds)
        self.start_hour_ist = int(start_hour_ist)
        self.end_hour_ist = int(end_hour_ist)

        # control fields for background task
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._wakeup = asyncio.Event()

        # observability
        self.last_run: Optional[datetime] = None
        self.last_summary: Optional[Dict[str, Any]] = None

    def _in_active_window(self) -> bool:
        """Return True if current IST hour is within configured active window."""
        now_utc = datetime.utcnow()
        ist_now = now_utc + timedelta(hours=5, minutes=30)
        return self.start_hour_ist <= ist_now.hour < self.end_hour_ist

    def _run_once(self) -> None:
        """
        Synchronous single iteration (safe to run in a threadpool).
        Mirrors your original __main__ logic.
        """
        logger.info("PeriodicJobRanker: starting run_once")
        mongo = None
        try:
            ranker = ResumeRanker()
            mongo = MongoService(db_name="algojobs")

            raw_jobs = mongo.get_all_jobs(limit=0) or []
            logger.info("Fetched %d jobs from Mongo", len(raw_jobs))

            jobs_validated: List[object] = []
            for j in raw_jobs:
                try:
                    if hasattr(Job, "model_validate"):
                        jobs_validated.append(Job.model_validate(j))
                    else:
                        jobs_validated.append(Job.parse_obj(j))
                except Exception:
                    logger.exception("Job validation failed - using raw dict fallback for job=%r", j)
                    jobs_validated.append(j)

            if not jobs_validated:
                logger.warning("No jobs found; skipping run")
                return

            svc = MultiJobRankingService(mongo=mongo, ranker=ranker)
            summary = svc.rank_all_jobs_and_upsert(jobs_validated)
            logger.info("run_once completed: %s", summary)

            self.last_run = datetime.utcnow()
            self.last_summary = summary

        except Exception:
            logger.exception("Error during run_once")
        finally:
            # ensure mongo closed (MultiJobRankingService used the same mongo instance)
            if mongo:
                try:
                    mongo.close()
                except Exception:
                    logger.exception("Error closing MongoService after run_once")
            logger.info("PeriodicJobRanker: run_once finished")

    async def run_now(self) -> None:
        """Async helper to run the job immediately (runs blocking work in a threadpool)."""
        await asyncio.to_thread(self._run_once)

    async def _loop(self) -> None:
        """Background loop that runs until stop() is called."""
        logger.info("PeriodicJobRanker: background loop started")
        try:
            while not self._stopping.is_set():
                try:
                    if self._in_active_window():
                        logger.debug("Within active IST window; scheduling run_once")
                        try:
                            await asyncio.to_thread(self._run_once)
                        except asyncio.CancelledError:
                            logger.info("PeriodicJobRanker: run cancelled")
                            raise
                        except Exception:
                            logger.exception("Unhandled exception during run_once")
                    else:
                        logger.debug("Outside active IST window; skipping run")

                    # Wait for wakeup or stop or timeout
                    wait_tasks = {
                        asyncio.create_task(self._stopping.wait()),
                        asyncio.create_task(self._wakeup.wait()),
                    }
                    try:
                        done, pending = await asyncio.wait(wait_tasks, timeout=self.interval_seconds, return_when=asyncio.FIRST_COMPLETED)
                    except asyncio.CancelledError:
                        logger.info("PeriodicJobRanker: loop cancelled during wait")
                        raise

                    # clear wakeup if it fired
                    if self._wakeup.is_set():
                        self._wakeup.clear()

                    # if stopping, break out
                    if self._stopping.is_set():
                        break

                    # cancel any pending tasks to avoid leaks
                    for t in pending:
                        t.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await t

                except asyncio.CancelledError:
                    logger.info("PeriodicJobRanker: background loop cancelled")
                    raise
                except Exception:
                    logger.exception("Error in PeriodicJobRanker loop")
        finally:
            logger.info("PeriodicJobRanker: background loop stopped")

    def start(self) -> None:
        """Start the background loop (idempotent)."""
        if self._task and not self._task.done():
            logger.debug("PeriodicJobRanker already running")
            return
        self._stopping.clear()
        self._wakeup.clear()
        self._task = asyncio.create_task(self._loop(), name="periodic_job_ranker")
        logger.info("PeriodicJobRanker: task scheduled")

    async def stop(self, wait_timeout: float = 10.0) -> None:
        """Stop the background loop and wait for it to finish (with timeout)."""
        if not self._task:
            logger.debug("PeriodicJobRanker not running")
            return
        logger.info("PeriodicJobRanker: stopping background task")
        self._stopping.set()
        self._wakeup.set()
        try:
            await asyncio.wait_for(self._task, timeout=wait_timeout)
        except asyncio.TimeoutError:
            logger.warning("PeriodicJobRanker did not stop in time, cancelling")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("PeriodicJobRanker cancelled")
        except asyncio.CancelledError:
            logger.info("PeriodicJobRanker stop() cancelled during shutdown")
        finally:
            self._task = None

    def is_running(self) -> bool:
        """Return True if background task is active."""
        return bool(self._task and not self._task.done())


# Example usage (run manually):
# if __name__ == "__main__":
#     pr = PeriodicJobRanker()
#     pr.start()
#     # ... later await pr.stop()
