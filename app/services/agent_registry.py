# app/services/agent_registry.py
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from app.services.agent_service import AgentManager

logger = logging.getLogger("AgentRegistry")

class AgentRegistry:
    def __init__(self, concurrency_limit: int = 10):
        self._registry: Dict[str, AgentManager] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    async def create_and_schedule(self, agent_name: str, entrypoint, start_time: datetime, **worker_kwargs):
        """
        Create AgentManager and schedule it to start at start_time.
        Returns the AgentManager instance and the scheduler task so caller may cancel.
        """
        async with self._lock:
            if agent_name in self._registry:
                raise RuntimeError("agent_name already exists")
            mgr = AgentManager(agent_name, entrypoint)
            self._registry[agent_name] = mgr

        now_utc = datetime.now(timezone.utc)
        delay = max((start_time - now_utc).total_seconds(), 0.0)

        async def _delayed_start():
            await asyncio.sleep(delay)
            # Acquire concurrency slot
            async with self._semaphore:
                started = await mgr.run_now(**worker_kwargs)
                if not started:
                    logger.warning("agent was already running at scheduled time")
                # wait until finished then cleanup registry entry
                while mgr.is_running():
                    await asyncio.sleep(1)
            # finished — cleanup
            async with self._lock:
                self._registry.pop(agent_name, None)

        task = asyncio.create_task(_delayed_start(), name=f"scheduler:{agent_name}")
        return mgr, task

    async def stop_agent(self, agent_name: str, timeout: float = 30.0) -> bool:
        async with self._lock:
            mgr = self._registry.get(agent_name)
        if not mgr:
            return True
        ok = await mgr.stop(timeout=timeout)
        async with self._lock:
            self._registry.pop(agent_name, None)
        return ok

    async def active_count(self) -> int:
        async with self._lock:
            return sum(1 for m in self._registry.values() if m.is_running())

# create a single global registry in your app startup
agent_registry = AgentRegistry(concurrency_limit=20)
