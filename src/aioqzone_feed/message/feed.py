from dataclasses import dataclass
from typing import Generic, TypeVar

from aioqzone.model import FeedData
from aioqzone.model.response.web import FeedRep
from tylisten import BaseMessage, Emitter
from tylisten.futstore import FutureStore

from aioqzone_feed.type import BaseFeed, FeedContent

_F = TypeVar("_F", FeedData, FeedRep)

__all__ = ["raw_feed", "processed_feed", "FeedApiEmitterMixin"]


@dataclass
class raw_feed(BaseMessage):
    bid: int
    """Used to identify feed batch (tell from different calling)."""
    feed: BaseFeed
    """Used to pass a ref to the feed."""


@dataclass
class processed_feed(BaseMessage):
    bid: int
    """Used to identify feed batch (tell from different calling)."""
    feed: FeedContent
    """Used to pass the feed content."""


class FeedApiEmitterMixin(Generic[_F]):
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.feed_dropped = Emitter(raw_feed)
        self.feed_processed = Emitter(processed_feed)
        self.feed_media_updated = Emitter(processed_feed)
        self.ch_dispatch = FutureStore()
        """A future store serves as feed dispatch channel."""
        self.ch_notify = FutureStore()
        """A future store serves as message notify channel."""

    async def stop_fetch(self, feed: _F) -> bool:
        """An async callback to determine if fetch should be stopped (after processing current batch)."""
        return False

    def stop(self):
        self.feed_dropped.abort()
        self.feed_processed.abort()
        self.feed_media_updated.abort()
        self.ch_dispatch.clear()
        self.ch_notify.clear()
