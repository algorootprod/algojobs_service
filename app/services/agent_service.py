# app/services/agent_manager.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Any

from livekit.agents import Worker, WorkerOptions
from app.core.config import config  # adjust if your config path differs

logger = logging.getLogger("AgentManager")
logger.setLevel(logging.INFO)


class AgentManager:
    """
    Minimal AgentManager for a single agent_name + provided entrypoint.
    - Construct with (agent_name: str, entrypoint: Callable[..., Any])
    - run_now() -> starts Worker.run()
    - schedule_in(delay_seconds) / schedule_at(start_time) -> schedule a future run
    - stop() -> attempt graceful shutdown via worker.aclose() and cancel the runner task
    """

    def __init__(self, agent_name: str, entrypoint: Callable[..., Any]):
        self.agent_name = agent_name
        self.entrypoint = entrypoint

        # Only one active run per AgentManager instance (per agent_name)
        self._runner_task: Optional[asyncio.Task] = None
        self._worker: Optional[Worker] = None

        # lock to avoid races on start/stop
        self._lock = asyncio.Lock()

    def _make_worker(self, **kwargs) -> Worker:
        """
        Create a Worker instance using WorkerOptions.
        This assumes you have LIVEKIT_URL/API_KEY/API_SECRET in config.
        If you need additional WorkerOptions values, pass them via kwargs.
        """
        opts = WorkerOptions(
            entrypoint_fnc=self.entrypoint,
            ws_url=getattr(config, "LIVEKIT_URL", None),
            agent_name=self.agent_name,
            api_key=getattr(config, "LIVEKIT_API_KEY", None),
            api_secret=getattr(config, "LIVEKIT_API_SECRET", None),
        )
        return Worker(opts=opts)

    async def run_now(self, **worker_kwargs) -> bool:
        """
        Start the agent immediately. Returns True if started, False if already running.
        worker_kwargs are forwarded to WorkerOptions creation.
        """
        async with self._lock:
            if self._runner_task and not self._runner_task.done():
                logger.warning(f"[{self.agent_name}] already running")
                return False

            async def _runner():
                worker = None
                try:
                    logger.info(f"[{self.agent_name}] creating Worker")
                    worker = self._make_worker(**worker_kwargs)
                    # expose worker so stop() can access it
                    async with self._lock:
                        self._worker = worker
                        # store reference to current asyncio Task
                        self._runner_task = asyncio.current_task()

                    logger.info(f"[{self.agent_name}] starting worker.run()")
                    # run() should block until the worker completes its lifecycle
                    await worker.run()
                    logger.info(f"[{self.agent_name}] worker.run() finished normally")
                except asyncio.CancelledError:
                    logger.info(f"[{self.agent_name}] runner task cancelled — attempting graceful aclose()")
                    if worker:
                        try:
                            await worker.aclose()
                            logger.info(f"[{self.agent_name}] worker.aclose() successful after cancel")
                        except Exception:
                            logger.exception(f"[{self.agent_name}] worker.aclose() failed during cancel")
                    raise
                except Exception:
                    logger.exception(f"[{self.agent_name}] unexpected exception in runner")
                finally:
                    # cleanup
                    async with self._lock:
                        self._worker = None
                        # if task is still the same stored task, clear it
                        if self._runner_task and self._runner_task.done():
                            self._runner_task = None
                        logger.info(f"[{self.agent_name}] cleaned up runner state")

            # create and store the task
            task = asyncio.create_task(_runner(), name=f"agent-runner:{self.agent_name}")
            self._runner_task = task
            logger.info(f"[{self.agent_name}] scheduled to run now")
            return True

    async def schedule_in(self, delay_seconds: float, **worker_kwargs) -> asyncio.Task:
        """
        Schedule agent start after delay_seconds. Returns the scheduling task (so caller may cancel it).
        """
        async def _delayed():
            try:
                logger.info(f"[{self.agent_name}] scheduled to start in {delay_seconds:.1f}s")
                await asyncio.sleep(max(0.0, delay_seconds))
                await self.run_now(**worker_kwargs)
            except asyncio.CancelledError:
                logger.info(f"[{self.agent_name}] scheduled start cancelled before launching")

        return asyncio.create_task(_delayed(), name=f"agent-scheduler:{self.agent_name}")

    async def schedule_at(self, start_time: datetime, **worker_kwargs) -> asyncio.Task:
        """
        Schedule the agent to start at a specific datetime.
        If naive datetime is passed, it is treated as local time.
        """
        if start_time.tzinfo is None:
            # interpret as local and convert to UTC offset-aware now comparison
            now = datetime.now()
        else:
            now = datetime.now(tz=start_time.tzinfo)
        delay = (start_time - now).total_seconds()
        delay = max(delay, 0.0)
        return await self.schedule_in(delay, **worker_kwargs)

    async def stop(self, timeout: float = 30.0) -> bool:
        """
        Gracefully stop the running worker:
         1. Try worker.aclose() if worker instance present.
         2. Cancel the runner task and wait up to `timeout` seconds.
        Returns True if stopped or not running, False if timed out.
        """
        async with self._lock:
            task = self._runner_task
            worker = self._worker

        if not task and not worker:
            logger.info(f"[{self.agent_name}] not running")
            return True

        # 1) attempt graceful aclose
        if worker is not None:
            try:
                logger.info(f"[{self.agent_name}] attempting worker.aclose() for graceful shutdown")
                maybe = worker.aclose()
                if asyncio.iscoroutine(maybe):
                    await maybe
                logger.info(f"[{self.agent_name}] worker.aclose() completed")
            except Exception:
                logger.exception(f"[{self.agent_name}] error during worker.aclose(); will cancel runner task")

        # 2) cancel runner task if present
        if task and not task.done():
            logger.info(f"[{self.agent_name}] cancelling runner task")
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=timeout)
                logger.info(f"[{self.agent_name}] runner task finished after cancel")
            except asyncio.TimeoutError:
                logger.warning(f"[{self.agent_name}] runner did not finish within {timeout}s")
                return False
            except asyncio.CancelledError:
                logger.info(f"[{self.agent_name}] runner cancelled successfully")

        # final cleanup
        async with self._lock:
            self._runner_task = None
            self._worker = None

        logger.info(f"[{self.agent_name}] stopped and cleaned up")
        return True

    async def stop_and_forget(self):
        """
        Force cleanup without waiting: attempt aclose, cancel task and clear references.
        Use with caution.
        """
        async with self._lock:
            task = self._runner_task
            worker = self._worker
            self._runner_task = None
            self._worker = None

        if worker is not None:
            try:
                await worker.aclose()
            except Exception:
                logger.exception(f"[{self.agent_name}] worker.aclose() failed in stop_and_forget")

        if task and not task.done():
            task.cancel()
        logger.info(f"[{self.agent_name}] forcefully stopped (fire-and-forget)")

    def is_running(self) -> bool:
        """
        Return whether the agent is currently running.
        """
        t = self._runner_task
        return bool(t and not t.done())
