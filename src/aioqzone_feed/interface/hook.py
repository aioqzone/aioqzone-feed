from aioqzone.interface.hook import Event
from aioqzone.type import FeedRep

from ..type import FeedContent


class FeedEvent(Event):
    async def FeedDropped(self, bid: int, feed: FeedRep | FeedContent):
        """
        The FeedDropped hook is called when a feed is dropped for hitting some rules (e.g. advertisement)

        :param bid: Used to identify the feed.
        :param feed: Used to pass a ref to the feed.
        """

        pass

    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        """
        The FeedProcEnd function is called when all processes must be done have finished
        (i.e. except for slow-api that cannot return at once, and may not matters a lot)

        :param bid: Used to identify the feed that is being processed.
        :param feed: Used to pass the feed content.
        """

        pass

    async def FeedMediaUpdate(self, feed: FeedContent):
        """
        The FeedMediaUpdate function is used to update the media of a feed.
        The :external:meth:`aioqzone.api.DummyQapi.floatview_photo_list` is one of the slow api.
        The media will be update by raw photos/videos, list order should not be changed

        :param feed: To tell which feed is updated. The feed itself is updated by ref already, the ref should have been passed by :meth:`.FeedProcEnd` in the past.
        """

        pass

    async def HeartbeatFailed(self, exc: BaseException | None = None):
        """
        The HeartbeatFailed function is called when the heartbeat fails.
        It can be used to log an error and call :meth:`aioqzone_feed.api.feed.FeedApi.add_heartbeat`
        again if possible.

        :param exc: Used to pass an exception object that can be used to determine the cause of the heartbeat failure.
        """

        pass
