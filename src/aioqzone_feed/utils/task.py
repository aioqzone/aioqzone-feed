import asyncio
import logging
from time import time
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AsyncTimer:
    task: Optional[asyncio.Task] = None
    last_call = 0.0

    def __init__(
        self,
        interval: float,
        func: Callable[[], Awaitable[bool]],
        *,
        name: Optional[str] = None,
        delay: float = 0.0,
    ) -> None:
        self.itvl = interval
        self.func = func
        self.delay = delay
        self.name = name or f"AsyncTimer: <{func.__name__}>"

    async def _loop(self):
        try:
            await asyncio.sleep(self.delay)
            self.last_call = time()
            stop = await self.func()
            while not stop:
                await asyncio.sleep(self.itvl)
                self.last_call = time()
                stop = await self.func()
        except asyncio.CancelledError:
            logger.info("%s cancelled.", self.name)
            return

    def __call__(self):
        self.task = asyncio.create_task(self._loop())
        return self.task

    @property
    def state(self):
        """`INIT` if not started (just initted).
        `PENDING`, `FINISHED` as that in :class:`asyncio.Task`"""
        return self.task._state if self.task else "INIT"

    def stop(self):
        if self.task:
            self.task.cancel()
            self.task = None

    def __repr__(self) -> str:
        return f"{self.name} ({self.state})"

    def change_interval(self, intv: float, stop=True):
        self.itvl = intv
        if stop and self.task and self.task._state == "PENDING":
            self.stop()
            self.delay = intv - (time() - self.last_call)
            self()
