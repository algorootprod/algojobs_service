import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Any, Tuple
from app.services.agent_service import AgentManager

logger = logging.getLogger("AgentRegistry")
logger.setLevel(logging.INFO)


class AgentRegistry:
    """
    Lightweight, production-ready registry for managing multiple AgentManager instances.
    Handles:
    - Scheduling start at a future time
    - Starting agents instantly
    - Concurrency limits (via semaphore)
    - Graceful stop and cleanup
    - Global shutdown support
    """

    def __init__(self, concurrency_limit: int = 10):
        self._registry: Dict[str, AgentManager] = {}
        # track scheduler / monitor tasks: scheduled starts and monitors for immediate starts
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._closed = False

    async def create_and_schedule(
        self,
        agent_name: str,
        entrypoint: Callable[..., Any],
        start_time: datetime,
        **worker_kwargs,
    ):
        """
        Create an AgentManager and schedule it to start at start_time.
        Returns (AgentManager, scheduler_task).
        """
        if self._closed:
            raise RuntimeError("AgentRegistry is shutting down")

        # Normalize time to UTC
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        start_time_utc = start_time.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        delay = max((start_time_utc - now_utc).total_seconds(), 0.0)

        async with self._lock:
            if agent_name in self._registry or agent_name in self._scheduled_tasks:
                raise RuntimeError(f"Agent {agent_name} already exists")

            mgr = AgentManager(agent_name, entrypoint)
            self._registry[agent_name] = mgr

        async def _delayed_start():
            try:
                if delay > 0:
                    logger.info(f"[{agent_name}] scheduled to start in {delay:.1f}s at {start_time_utc.isoformat()}")
                    await asyncio.sleep(delay)

                async with self._semaphore:
                    started = await mgr.run_now(**worker_kwargs)
                    if not started:
                        logger.warning(f"[{agent_name}] already running at scheduled time")

                    # Wait for agent to finish
                    while mgr.is_running():
                        await asyncio.sleep(1)

                logger.info(f"[{agent_name}] finished execution")
            except asyncio.CancelledError:
                logger.info(f"[{agent_name}] scheduled task cancelled")
                raise
            except Exception:
                logger.exception(f"[{agent_name}] unexpected error during run")
            finally:
                async with self._lock:
                    self._scheduled_tasks.pop(agent_name, None)
                    self._registry.pop(agent_name, None)
                    logger.info(f"[{agent_name}] cleaned up from registry")

        task = asyncio.create_task(_delayed_start(), name=f"scheduler:{agent_name}")
        async with self._lock:
            self._scheduled_tasks[agent_name] = task

        return mgr, task

    async def start_now(
        self,
        agent_name: str,
        entrypoint: Callable[..., Any],
        **worker_kwargs,
    ) -> Tuple[AgentManager, bool]:
        """
        Start an agent immediately (respecting concurrency limit).
        Returns (AgentManager, started) where `started` is True if run was started,
        False if an existing manager was already running.
        The registry will keep a short-lived monitor task to cleanup when the agent finishes.
        """
        if self._closed:
            raise RuntimeError("AgentRegistry is shutting down")

        async with self._lock:
            # if agent already exists and running, don't start another
            existing = self._registry.get(agent_name)
            if existing and existing.is_running():
                logger.warning(f"[{agent_name}] already exists and is running")
                return existing, False

            # create and store manager (either new or replace stale)
            mgr = AgentManager(agent_name, entrypoint)
            self._registry[agent_name] = mgr

        # Acquire a concurrency slot and start the worker
        started = False
        async with self._semaphore:
            started = await mgr.run_now(**worker_kwargs)
            if not started:
                logger.warning(f"[{agent_name}] run_now returned False (already running?)")

        # spawn monitor task to cleanup when run completes (so we behave like scheduled runs)
        async def _monitor():
            try:
                while mgr.is_running():
                    await asyncio.sleep(1)
                logger.info(f"[{agent_name}] monitor detected run finished")
            except asyncio.CancelledError:
                logger.info(f"[{agent_name}] monitor cancelled")
                raise
            finally:
                async with self._lock:
                    # remove registry entry and this monitor task
                    self._scheduled_tasks.pop(agent_name, None)
                    self._registry.pop(agent_name, None)
                    logger.info(f"[{agent_name}] cleaned up from registry by monitor")

        monitor_task = asyncio.create_task(_monitor(), name=f"monitor:{agent_name}")
        async with self._lock:
            # allow monitor to be cancelled via stop_agent if needed
            self._scheduled_tasks[agent_name] = monitor_task

        return mgr, bool(started)

    async def stop_agent(self, agent_name: str, timeout: float = 30.0) -> bool:
        """
        Stops a running agent and cancels any scheduled start/monitor.
        Returns True if stopped or already gone.
        """
        async with self._lock:
            sched_task = self._scheduled_tasks.pop(agent_name, None)
            mgr = self._registry.get(agent_name)

        # Cancel scheduled start or monitor if not yet completed
        if sched_task and not sched_task.done():
            sched_task.cancel()
            try:
                await asyncio.wait_for(sched_task, timeout=5.0)
            except Exception:
                pass
            logger.info(f"[{agent_name}] cancelled scheduled start/monitor")

        if not mgr:
            return True

        ok = await mgr.stop(timeout=timeout)

        async with self._lock:
            self._registry.pop(agent_name, None)

        logger.info(f"[{agent_name}] stopped and removed from registry")
        return ok

    async def active_count(self) -> int:
        """Return number of currently running agents."""
        async with self._lock:
            return sum(1 for m in self._registry.values() if m.is_running())

    async def stop_all(self, timeout: float = 30.0):
        """Stops all agents and cancels all scheduled starts/monitors."""
        async with self._lock:
            agents = list(self._registry.keys())
            scheduled = list(self._scheduled_tasks.keys())

        logger.info(f"Stopping all agents ({len(agents)}) and scheduled tasks ({len(scheduled)})")

        for name in scheduled:
            await self.stop_agent(name, timeout=timeout)

        for name in agents:
            await self.stop_agent(name, timeout=timeout)

        logger.info("All agents stopped successfully")

    async def shutdown(self, timeout: float = 30.0):
        """Call this during FastAPI shutdown event."""
        if self._closed:
            return
        self._closed = True
        logger.info("AgentRegistry shutting down...")
        await self.stop_all(timeout=timeout)
        logger.info("AgentRegistry shutdown complete")


# Create global singleton instance
agent_registry = AgentRegistry(concurrency_limit=20)
