import asyncio
import logging
from time import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AsyncTimer:
    task: Optional[asyncio.Task]
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
            stop = await self.func()
            self.last_call = time()
            while not stop:
                await asyncio.sleep(self.itvl)
                stop = await self.func()
                self.last_call = time()
        except asyncio.CancelledError:
            logger.info("%s cancelled.", self.name)
            return

    def __call__(self):
        self.task = asyncio.create_task(self._loop(), name=self.name)
        return self.task

    @property
    def state(self):
        return self.task._state if self.task else "init"

    def stop(self):
        if self.task:
            return self.task.cancel()
        return True

    def __repr__(self) -> str:
        return f"{self.name} ({self.state})"
