import asyncio
from aioqzone.interface.hook import Event
from ..type import FeedContent


class FeedEvent(Event):
    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        pass

    async def FeedMediaUpdate(self, feed: FeedContent):
        pass
