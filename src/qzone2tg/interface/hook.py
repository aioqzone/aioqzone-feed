import asyncio
from aioqzone.interface.hook import Event
from ..type import FeedModel


class FeedEvent(Event):
    async def FeedProcEnd(self, task: asyncio.Task[tuple[int, FeedModel]]):
        pass
