from typing import Union

from aioqzone.type.resp import FeedRep
from qqqr.event import Event

from ..type import FeedContent


class FeedEvent(Event):
    TY_BID = int

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

    async def StopFeedFetch(self, feed: FeedRep) -> bool:
        """Used to judge if a feed fetching loop should break. Once this hook returns `True`, new pages will
        not be fetched any more. Note that the rest feeds of current page may still trigger `FeedProcEnd`.

        This is used to replace the ``exceed_pred`` paramater of `FeedApi.get_feeds_by_second`.
        This will also be used in `FeedApi.get_feeds_by_count`.

        .. versionadded:: 0.12.0
        """
        return False
