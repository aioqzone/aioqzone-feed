from aioqzone.interface.hook import Event
from aioqzone.type import FeedRep


class FeedEvent(Event):
    async def BatchArrive(self, feeds: dict[int, FeedRep]):
        pass
