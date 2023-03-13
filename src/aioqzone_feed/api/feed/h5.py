import asyncio
import logging
import time
from typing import Optional

from aioqzone.api import Loginable
from aioqzone.api.h5 import QzoneH5API
from aioqzone.exception import LoginError, QzoneError
from aioqzone.type.resp.h5 import FeedData
from exceptiongroup import ExceptionGroup
from httpx import HTTPStatusError
from qqqr.event import Emittable, hook_guard
from qqqr.exception import UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.heartbeat import HeartbeatApi
from aioqzone_feed.event import FeedEvent
from aioqzone_feed.type import FeedContent

log = logging.getLogger(__name__)
login_exc = (LoginError, UserBreak, asyncio.CancelledError)


class FeedH5Api(QzoneH5API, Emittable[FeedEvent]):
    """
    .. versionadded:: 0.13.0
    """

    def __init__(self, client: ClientAdapter, loginman: Loginable, *, init_hb=True):
        super().__init__(client, loginman)
        self.bid = -1
        if init_hb:
            self.hb_api = HeartbeatApi(self)

    def new_batch(self) -> FeedEvent.TY_BID:
        """
        The new_batch function edit internal batch id and return it.

        A batch id can be used to identify a batch, thus even the same feed can have different id e.g. `(bid, uin, abstime)`.

        :rtype: :obj:`FeedEvent.TY_BID`
        :return: The batch_id.
        """

        self.bid += 1
        return self.bid

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, max as 10, defaults to 10

        :raises `qqqr.exception.UserBreak`: qr login canceled
        :raises `aioqzone.exception.LoginError`: not logined
        :raises `ExceptionGroup`: max error time exceeds
        :raises `SystemExit`: unexcpected error

        :return: feeds num got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        stop_fetching = False
        got = 0
        aux = ""
        exceed_pred = hook_guard(self.hook.StopFeedFetch)
        err = []
        for page in range(1000):
            try:
                resp = await self.get_active_feeds(aux)
            except (QzoneError, HTTPStatusError) as e:
                err.append(e)
                log.warning(f"Error when fetching page. Skipped. {e}")
                if len(err) >= 5:
                    raise ExceptionGroup("max error exceeds", err)
                await asyncio.sleep(0.5)
                continue

            aux = resp.attachinfo
            for fd in resp.vFeeds[: count - got]:
                if await exceed_pred(fd):
                    stop_fetching = True
                    continue
                self._dispatch_feed(fd)
                got += 1
            if stop_fetching or got >= count or not resp.hasmore:
                break
        return got

    async def get_feeds_by_second(
        self,
        seconds: float,
        start: Optional[float] = None,
    ) -> int:
        """Get feeds by abstime (seconds). Range: [`start` - `seconds`, `start`].

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.
        :param exceed_pred: another criterion to judge if the feed is out of range, defaults to None

        :raises `qqqr.exception.UserBreak`: qr login canceled
        :raises `aioqzone.exception.LoginError`: not logined
        :raises `ExceptionGroup`: max error time exceeds
        :raises `SystemExit`: unexcpected error

        :return: feeds num got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        start = start or time.time()
        end = start - seconds
        stop_fetching = False
        got = 0
        aux = ""
        exceed_pred = hook_guard(self.hook.StopFeedFetch)
        err = []
        for page in range(1000):
            try:
                resp = await self.get_active_feeds(aux)
            except (QzoneError, HTTPStatusError) as e:
                err.append(e)
                log.warning(f"Error when fetching page. Skipped. {e}")
                if len(err) >= 5:
                    raise ExceptionGroup("max error exceeds", err)
                await asyncio.sleep(0.5)
                continue

            aux = resp.attachinfo
            for fd in resp.vFeeds:
                if fd.abstime > start:
                    continue
                if fd.abstime < end or await exceed_pred(fd):
                    stop_fetching = True
                    continue
                self._dispatch_feed(fd)
                got += 1
            if stop_fetching or not resp.hasmore:
                break
        return got

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

        if feed.cellid.startswith("advertisement"):
            log.info(f"advertisement rule hit: {feed.cellid}")
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
        model = FeedContent.from_feed(feed)

        if self.drop_rule(feed):
            FeedContent.from_feed(feed)
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, model))
            return

        model.set_detail(feed)
        self.add_hook_ref("hook", self.hook.FeedProcEnd(self.bid, model))

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("FeedApi stopping...")
        self.clear(*self._tasks.keys())
        if hasattr(self, "hb_api"):
            self.hb_api.stop()
