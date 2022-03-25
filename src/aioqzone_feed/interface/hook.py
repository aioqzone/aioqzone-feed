from typing import Optional, Union

from aioqzone.interface.hook import Event
from aioqzone.type import FeedRep

from ..type import FeedContent

TY_BID = int


class FeedEvent(Event):
    async def FeedDropped(self, bid: TY_BID, feed: Union[FeedRep, FeedContent]):
        """
        The FeedDropped hook is called when a feed is dropped for hitting some rules (e.g. advertisement)

        :param bid: Used to identify feed batch (tell from different calling).
        :param feed: Used to pass a ref to the feed.
        """

        pass

    async def FeedProcEnd(self, bid: TY_BID, feed: FeedContent):
        """
        The FeedProcEnd function is called when all processes must be done have finished
        (i.e. except for slow-api that cannot return at once, and may not matters a lot)

        :param bid: Used to identify feed batch (tell from different calling).
        :param feed: Used to pass the feed content.
        """

        pass

    async def FeedMediaUpdate(self, bid: TY_BID, feed: FeedContent):
        """
        The FeedMediaUpdate function is used to update the media of a feed.
        The :external:meth:`aioqzone.api.DummyQapi.floatview_photo_list` is one of the slow api.
        The media will be update by raw photos/videos, list order should not be changed

        :param bid: Used to identify feed batch (tell from different calling).
        :param feed: To tell which feed is updated. The feed itself is updated by ref already, the ref should have been passed by :meth:`.FeedProcEnd` in the past.
        """

        pass

    async def HeartbeatFailed(self, exc: Optional[BaseException] = None):
        """
        The HeartbeatFailed function is called when the heartbeat fails.
        It can be used to log an error and call :meth:`aioqzone_feed.api.feed.FeedApi.add_heartbeat`
        again if possible.

        :param exc: Used to pass an exception object that can be used to determine the cause of the heartbeat failure.
        """

        pass

    async def HeartbeatRefresh(self, num: int):
        """This event is triggered after a heartbeat succeeded and there are new feeds.
        Use this event to wait for all dispatch task to be finished, and send received feeds.

        :param num: number of new feeds

        Example:

        .. code-block:: python

            async def HeartbeatRefresh(self, num: int):
                await api.get_feeds_by_count(num)
                await api.wait()        # wait for all dispatch tasks and hook tasks
                await queue.send_all()  # send received feeds
        """
        pass
