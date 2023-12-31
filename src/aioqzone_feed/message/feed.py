import typing as t

from tylisten import hookdef
from tylisten.futstore import FutureStore

from aioqzone_feed.type import FEED_TYPES, BaseFeed, FeedContent

__all__ = ["raw_feed", "processed_feed", "stop_fetch", "FeedApiEmitterMixin"]


@hookdef
def raw_feed(bid: int, feed: BaseFeed) -> t.Any:
    """
    :param bid: Used to identify feed batch (tell from different calling).
    :param feed: Used to pass a ref to the feed.
    """


@hookdef
def processed_feed(bid: int, feed: FeedContent) -> t.Any:
    """
    :param bid: Used to identify feed batch (tell from different calling).
    :param feed: Used to pass the feed content.
    """


@hookdef
def stop_fetch(feed: FEED_TYPES) -> bool:
    """An async callback to determine if fetch should be stopped (after processing current batch)."""
    return False


class FeedApiEmitterMixin:
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.feed_dropped = raw_feed()
        """This emitter is triggered when a feed is dropped."""
        self.feed_processed = processed_feed()
        """This emitter is triggered when a feed is processed."""
        self.feed_media_updated = processed_feed()
        """This emitter is triggered when a feed's media is updated."""
        self.stop_fetch = stop_fetch()
        """This hook is used to determin whether a fetch should stop."""
        self._ch_feed_dispatch = FutureStore()
        """An internal future store serves as feed dispatch channel."""
        self.ch_feed_notify = FutureStore()
        """A future store serves as message notify channel."""

    def stop(self):
        """Clear future stores."""
        self._ch_feed_dispatch.clear()
        self.ch_feed_notify.clear()
