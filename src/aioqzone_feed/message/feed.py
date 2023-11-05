from aioqzone.model import FeedData
from tylisten import hookdef
from tylisten.futstore import FutureStore

from aioqzone_feed.type import BaseFeed, FeedContent

__all__ = ["raw_feed", "processed_feed", "FeedApiEmitterMixin"]


@hookdef
def raw_feed(bid: int, feed: BaseFeed):
    """
    :param bid: Used to identify feed batch (tell from different calling).
    :param feed: Used to pass a ref to the feed.
    """


@hookdef
def processed_feed(bid: int, feed: FeedContent):
    """
    :param bid: Used to identify feed batch (tell from different calling).
    :param feed: Used to pass the feed content.
    """


class FeedApiEmitterMixin:
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.feed_dropped = raw_feed()
        self.feed_processed = processed_feed()
        self.feed_media_updated = processed_feed()
        self.ch_feed_dispatch = FutureStore()
        """A future store serves as feed dispatch channel."""
        self.ch_feed_notify = FutureStore()
        """A future store serves as message notify channel."""

    async def stop_fetch(self, feed: FeedData) -> bool:
        """An async callback to determine if fetch should be stopped (after processing current batch)."""
        return False

    def stop(self):
        self.ch_feed_dispatch.clear()
        self.ch_feed_notify.clear()
