import logging
import time
import typing as t

from aioqzone.model import FeedData

from aioqzone_feed.api.heartbeat import HeartbeatApi
from aioqzone_feed.message import FeedApiEmitterMixin
from aioqzone_feed.type import FeedContent

log = logging.getLogger(__name__)
MAX_BID = 0x7FFF
"""The max batch id.

.. versionadded:: 0.14.1
"""


class FeedH5Api(FeedApiEmitterMixin, HeartbeatApi):
    """
    .. versionadded:: 0.13.0
    """

    bid = 0

    def new_batch(self) -> int:
        """
        The new_batch function edit internal batch id and return it.

        A batch id can be used to identify a batch, thus even the same feed can have different id e.g. `(bid, uin, abstime)`.

        :return: The batch_id.
        """

        self.bid = (self.bid + 1) % MAX_BID
        return self.bid

    async def _get_feeds_by_pred(
        self,
        stop_pred: t.Callable[[FeedData, int], bool],
        filter_pred: t.Optional[t.Callable[[FeedData], bool]] = None,
    ):
        """
        :meta public:
        :return: number of feeds that we have fetched actually.

        :raise `tenacity.RetryError`: Exception from :meth:`.get_active_feeds`.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        stop_fetching = False
        attach_info = ""
        cnt_got = 0

        while not stop_fetching:
            resp = await self.get_active_feeds(attach_info)
            attach_info = resp.attachinfo
            feeds = resp.vFeeds
            stop_fetching = not resp.hasmore

            log.debug(attach_info, extra=dict(got=cnt_got))

            for fd in feeds:
                if filter_pred and filter_pred(fd):
                    continue
                if stop_pred(fd, cnt_got) or await self.stop_fetch(fd):
                    stop_fetching = True
                    continue
                cnt_got += 1
                self._dispatch_feed(fd)

        return cnt_got

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, max as 10, defaults to 10

        .. seealso:: :meth:`._get_feeds_by_pred`.
        """
        if count <= 0:
            return 0
        count = min(count, 10)
        return await self._get_feeds_by_pred(lambda _, cnt: cnt >= count)

    async def get_feeds_by_second(
        self,
        seconds: float,
        start: t.Optional[float] = None,
    ) -> int:
        """Get feeds by abstime (seconds). Range: [`start` - `seconds`, `start`].

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.

        .. seealso:: :meth:`._get_feeds_by_pred`.
        """
        if seconds <= 0:
            return 0

        start = start or time.time()
        end = start - seconds

        if end > time.time():
            return 0

        return await self._get_feeds_by_pred(
            lambda feed, _: feed.abstime < end, lambda feed: feed.abstime > start
        )

    def drop_rule(self, feed: FeedData) -> bool:
        """Drop feeds according to some rules.
        No need to emit :meth:`FeedEvent.FeedDropped` event, it is handled by :meth:`_dispatch_feed`.

        Subclasses may inherit this method to customize their own rules.

        :param feed: the feed
        :return: if the feed is dropped.
        """
        if feed.userinfo.uin == 20050606:
            log.info(f"advertisement rule hit: {feed.userinfo.uin}")
            log.debug(f"Dropped: {feed}")
            return True

        if feed.fid.startswith("advertisement"):
            log.info(f"advertisement rule hit: {feed.fid}")
            log.debug(f"Dropped: {feed}")
            return True

        return False

    def _dispatch_feed(self, feed: FeedData) -> None:
        """dispatch feed according to api support.

        1. Drop feed according to rules defined in `drop_rule`, trigger :meth:`FeedDropped` hook if dropped;
        2. Get more if `hasmore` flag is set to ``1`` (Not Implemented yet);
        3. Trigger :meth:`FeedProcEnd` for prcocessed feeds.

        :param feed: feed
        """
        if feed.summary.hasmore:
            self.ch_feed_dispatch.add_awaitable(
                self.shuoshuo(feed.fid, feed.userinfo.uin, feed.common.appid)
            ).add_done_callback(lambda t: self._dispatch_feed(t.result()))
            return

        model = FeedContent.from_feed(feed)

        if self.drop_rule(feed):
            FeedContent.from_feed(feed)
            self.ch_feed_dispatch.add_awaitable(self.feed_dropped.results(self.bid, model))
            return

        model.set_detail(feed)
        self.ch_feed_notify.add_awaitable(self.feed_processed.results(self.bid, model))

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("FeedApi stopping...")
        FeedApiEmitterMixin.stop(self)
        HeartbeatApi.stop(self)
