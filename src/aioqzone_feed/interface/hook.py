from typing import Union

from aioqzone.interface.hook import Event
from aioqzone.type import FeedRep
from aioqzone.type import FeedsCount

from ..type import FeedContent


class FeedEvent(Event):
    async def FeedDropped(self, bid: int, feed: Union[FeedRep, FeedContent]):
        pass

    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        pass

    async def FeedMediaUpdate(self, feed: FeedContent):
        pass

    async def Heartbeat(self, count: FeedsCount):
        pass
