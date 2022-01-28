from aioqzone.interface.hook import Event
from aioqzone.type import FeedsCount

from ..type import FeedContent


class FeedEvent(Event):
    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        pass

    async def FeedMediaUpdate(self, feed: FeedContent):
        pass

    async def Heartbeat(self, count: FeedsCount):
        pass
