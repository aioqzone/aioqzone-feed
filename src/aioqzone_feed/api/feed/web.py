"""
.. versionchanged:: 0.13.0

    Import this module needs aioqzone extra ``lxml`` to be installed.
"""

import asyncio
import logging
import sys
import time
from typing import Any, Callable, Optional, TypeVar

from aioqzone.api import Loginable, QzoneWebAPI
from aioqzone.exception import CorruptError, LoginError, QzoneError, SkipLoginInterrupt
from aioqzone.type.internal import AlbumData
from aioqzone.type.resp import FeedDetailRep, FeedRep, PicRep
from aioqzone.utils.catch import HTTPStatusErrorDispatch, QzoneErrorDispatch
from aioqzone.utils.html import HtmlContent, HtmlInfo
from httpx import HTTPError, HTTPStatusError
from lxml.html import HtmlElement, fromstring
from pydantic import ValidationError
from qqqr.event import Emittable, hook_guard
from qqqr.exception import HookError, UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.heartbeat import HeartbeatApi
from aioqzone_feed.event import FeedEvent
from aioqzone_feed.type import FeedContent, VisualMedia

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

log = logging.getLogger(__name__)
login_exc = (LoginError, UserBreak, asyncio.CancelledError)

T = TypeVar("T")


def add_done_callback(task, cb):
    # type: (asyncio.Future[T], Callable[[Optional[T]], Any]) -> asyncio.Future[T]
    def safe_unpack(task):
        # type: (asyncio.Future[T]) -> Optional[T]
        try:
            return task.result()
        except (
            QzoneError,
            HTTPStatusError,
            SkipLoginInterrupt,
            KeyboardInterrupt,
            UserBreak,
            CorruptError,
        ) as e:
            log.warning(f"{e.__class__.__name__} caught in {task}.")
            log.debug("", exc_info=e)
        except HookError as e:
            log.error(f"Error occurs in {e.hook}", exc_info=e)
        except (
            HTTPError,
            LoginError,
            asyncio.CancelledError,
        ) as e:
            log.warning(f"{e.__class__.__name__} caught.", exc_info=e)
        except SystemExit:
            raise
        except RuntimeError as e:
            if e.args[0] == "Session is closed":
                log.error(f"DEBUG: {task}", exc_info=True)
            else:
                raise
        except:
            log.fatal("Uncaught Exception!", exc_info=True)
            exit(1)

    task.add_done_callback(lambda t: cb(safe_unpack(t)))
    return task


class exc_stack:
    def __init__(self, max_len: int = 5) -> None:
        self._exc = []  # type: list[Exception]
        self.max_len = max_len

    def append(self, e: Exception):
        self._exc.append(e)
        if len(self._exc) >= self.max_len:
            raise ExceptionGroup("max retry exceeds", self._exc)


class FeedWebApi(QzoneWebAPI, Emittable[FeedEvent]):
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

        :raise `qqqr.exception.UserBreak`: qr login canceled
        :raise `aioqzone.exception.LoginError`: not logined
        :raise `QzoneError`: when code != -3000
        :raise `HTTPStatusError`: when code != 403
        :raise `ExceptionGroup`: max retry exceeds

        :return: feeds num got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.

        .. versionchanged:: 0.12.0

            `FeedEvent.StopFeedFetch` works in this method as well.
        """
        exceed_pred = hook_guard(self.hook.StopFeedFetch)
        stop_fetching = False
        got = 0
        aux = None
        errs = exc_stack()
        feeds = []

        def error_dispatch(e):
            feeds.clear()
            errs.append(e)
            log.warning(f"error fetching page: {e}")

        for page in range(1000):
            with QzoneErrorDispatch() as qse, HTTPStatusErrorDispatch() as hse:
                qse.dispatch(-3000, dispatcher=error_dispatch)
                hse.dispatch(403, dispatcher=error_dispatch)
                resp = await self.feeds3_html_more(page, count=count - got, aux=aux)
                aux = resp.aux
                feeds = resp.feeds
                stop_fetching = not aux.hasMoreFeeds

            log.debug(aux, extra=dict(got=got))

            for fd in feeds[: count - got]:
                if await exceed_pred(fd):
                    stop_fetching = True
                    continue
                if (got := got + 1) >= count:
                    stop_fetching = True
                    break
                self._dispatch_feed(fd)

            if stop_fetching:
                break

        return got

    async def get_feeds_by_second(
        self,
        seconds: float,
        start: Optional[float] = None,
    ) -> int:
        """Get feeds by abstime (seconds). Range: `[start - second, start]`.

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.
        :param exceed_pred: another criterion to judge if the feed is out of range, defaults to None

        :raise `qqqr.exception.UserBreak`: qr login canceled
        :raise `aioqzone.exception.LoginError`: not logined
        :raise `QzoneError`: when code != -3000
        :raise `HTTPStatusError`: when code != 403
        :raise `ExceptionGroup`: max retry exceeds

        :return: feeds num got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.

        .. versionchanged:: 0.12.0

            removed ``exceed_pred``, use `FeedEvent.StopFeedFetch` instead.
        """
        start = start or time.time()
        end = start - seconds
        stop_fetching = False
        got = 0
        aux = None
        exceed_pred = hook_guard(self.hook.StopFeedFetch)
        errs = exc_stack()
        feeds = []

        def error_dispatch(e):
            feeds.clear()
            errs.append(e)
            log.warning(f"error fetching page: {e}")

        for page in range(1000):
            with QzoneErrorDispatch() as qse, HTTPStatusErrorDispatch() as hse:
                qse.dispatch(-3000, dispatcher=error_dispatch)
                hse.dispatch(403, dispatcher=error_dispatch)
                resp = await self.feeds3_html_more(page, aux=aux)
                aux = resp.aux
                feeds = resp.feeds
                stop_fetching = not aux.hasMoreFeeds

            log.debug(aux, extra=dict(got=got))

            for fd in feeds:
                if fd.abstime > start:
                    continue
                if fd.abstime < end or await exceed_pred(fd):
                    stop_fetching = True
                    continue
                got += 1
                self._dispatch_feed(fd)

            if stop_fetching:
                break

        return got

    def drop_rule(self, feed: FeedRep) -> bool:
        """Drop feeds according to some rules.
        Dropping a feed will trigger :meth:`FeedEvent.FeedDropped` event.

        Subclasses may inherit this method to customize their own rules.

        :param feed: the feed
        :return: if the feed is dropped.
        """
        if feed.uin == 20050606:
            log.info(f"advertisement rule hit: {feed.uin}")
            log.debug(f"Dropped: {feed}")
            return True

        if feed.fid.startswith("advertisement"):
            log.info(f"advertisement rule hit: {feed.fid}")
            log.debug(f"Dropped: {feed}")
            return True

        return False

    def _dispatch_feed(self, feed: FeedRep) -> None:
        """dispatch feed according to api support.

        1. Call emotion_msgdetail for supported appid
        2. Else parse html content from response
        3. Full the html by calling emotion_getcomments if it's cutted
        4. Update media by calling floatview_photo_list if html contains thumbnail.

        All api that must be scheduled during this batch transaction must be added into
        `dispatch` task set. Other api which can be called later or has low-priority should
        be added into `slowapi` set.

        :param feed: feed
        """
        model = FeedContent.from_feed(feed)

        if self.drop_rule(feed):
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, model))
            return

        has_cur = [311]

        try:
            root, htmlinfo = HtmlInfo.from_html(feed.html)
        except ValidationError:
            log.debug("HtmlInfo ValidationError, html=%s", feed.html, exc_info=True)
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, model))
            return
        model.set_frominfo(htmlinfo)

        if model.appid in has_cur or model.curkey and model.curkey.startswith("http"):
            # optimize for feeds, no need to parse html content
            return self.__optimize_dispatch(feed, model, htmlinfo, root)
        self.__default_dispatch(feed, model, htmlinfo, root)

    def __optimize_dispatch(
        self, feed: FeedRep, model: FeedContent, htmlinfo: HtmlInfo, root: HtmlElement
    ):
        """Optimized feed processing: request for `emotion_msgdetail` api directly."""

        def detail_procs(dt: Optional[FeedDetailRep]):
            if not dt:
                return self.__default_dispatch(feed, model, htmlinfo, root)

            if dt.pic and not all(i.valid_url() for i in dt.pic):
                return self.__default_dispatch(feed, model, htmlinfo, root)

            model.set_detail(dt)
            self.add_hook_ref("hook", self.hook.FeedProcEnd(self.bid, model))

        get_full = self.add_hook_ref("dispatch", self.emotion_msgdetail(feed.uin, feed.fid))
        add_done_callback(get_full, detail_procs)

    def __default_dispatch(
        self, feed: FeedRep, model: FeedContent, htmlinfo: HtmlInfo, root: HtmlElement
    ):
        """Default feed processing: Parse info from html feed. If media is detected,
        then request for `floatview_photo_list` album api.
        """

        # has to parse html now
        # TODO: HtmlContent.from_html is risky
        def html_content_procs(root: HtmlElement):
            htmlct = HtmlContent.from_html(root, feed.uin)
            model.set_detail(htmlct)
            if htmlinfo.unikey:
                model.forward = htmlinfo.unikey
            self.add_hook_ref("hook", self.hook.FeedProcEnd(self.bid, model))
            self._add_mediaupdate_task(model, htmlct)

        if htmlinfo.complete:
            html_content_procs(root)
            return

        def full_html_procs(full: Optional[str]):
            if full:
                full_root = fromstring(full)
            else:
                full_root = root
            html_content_procs(full_root)

        get_full = self.add_hook_ref(
            "dispatch", self.emotion_getcomments(feed.uin, feed.fid, htmlinfo.feedstype)
        )
        add_done_callback(get_full, full_html_procs)

    def _add_mediaupdate_task(self, model: FeedContent, content: HtmlContent) -> None:
        if not (content.album and content.pic):
            return

        task = self.add_hook_ref(
            "slowapi", self.__fv_retry(model, content, self.bid, content.album, len(content.pic))
        )
        log.info(f"Media update task registered: {task}")

    async def __fv_retry(
        self, model: FeedContent, content: HtmlContent, bid: int, album: AlbumData, num: int
    ):
        assert content.album
        assert content.pic

        for i in range(12):
            st = 2**i - 1
            log.debug(f"sleep {st}s")
            await asyncio.sleep(st)
            try:
                fv = await self.floatview_photo_list(album, num)
                break
            except QzoneError as e:
                if e.code == -10001:
                    log.info(f"{str(e)}, retry={i + 1}")
                else:
                    log.info(f"Error in floatview_photo_list, retry={i + 1}")
                log.debug(e)
                continue
            except HTTPStatusError as e:
                log.info(f"Error in floatview_photo_list, retry={i + 1}")
                log.debug(e)
                continue
            except CorruptError:
                log.warning(f"Photo corrupt!")
                continue
            except login_exc:
                return
            except:
                log.fatal("unexpected exception in fv_retry", exc_info=True)
                return
        else:
            return
        model.media = [VisualMedia.from_pic(PicRep.from_floatview(i)) for i in fv]
        self.add_hook_ref("hook", self.hook.FeedMediaUpdate(bid, model))

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("FeedApi stopping...")
        self.clear(*self._tasks.keys())
        if hasattr(self, "hb_api"):
            self.hb_api.stop()
