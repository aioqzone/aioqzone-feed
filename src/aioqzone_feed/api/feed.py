import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional, Set, Tuple, TypeVar

import aioqzone.api as qapi
from aioqzone.api.loginman import QrStrategy
from aioqzone.event.login import Loginable
from aioqzone.exception import CorruptError, LoginError, QzoneError, SkipLoginInterrupt
from aioqzone.type.internal import AlbumData
from aioqzone.type.resp import FeedDetailRep, FeedRep, PicRep
from aioqzone.utils.html import HtmlContent, HtmlInfo
from httpx import HTTPError, HTTPStatusError
from pydantic import ValidationError
from qqqr.event import Emittable
from qqqr.exception import UserBreak
from qqqr.utils.net import ClientAdapter

from ..interface.hook import TY_BID, FeedEvent
from ..type import FeedContent, VisualMedia
from ..utils.task import AsyncTimer
from .emoji import trans_detail, trans_html

log = logging.getLogger(__name__)
login_exc = (LoginError, UserBreak, asyncio.CancelledError)

T = TypeVar("T")


def add_done_callback(task, cb):
    # type: (asyncio.Task[T], Callable[[Optional[T]], Any]) -> asyncio.Task[T]
    def safe_unpack(task):
        # type: (asyncio.Task[T]) -> Optional[T]
        try:
            return task.result()
        except QzoneError as e:
            lg = log.debug if e.code in [-10029] else log.error
            lg(f"DEBUG: {task}", exc_info=True)
        except HTTPStatusError:
            log.error(f"DEBUG: {task}", exc_info=True)
        except LoginError as e:
            log.error(f"LoginError: {e}")
            raise e
        except UserBreak as e:
            log.info("UserBreak captured!")
            raise e
        except SystemExit as e:
            raise e
        except RuntimeError as e:
            if e.args[0] == "Session is closed":
                log.error(f"DEBUG: {task}", exc_info=True)
            else:
                raise e
        except:
            log.fatal("Uncaught Exception!", exc_info=True)
            exit(1)

    task.add_done_callback(lambda t: cb(safe_unpack(t)))
    return task


class FeedApi(Emittable[FeedEvent]):
    hb_timer = None

    def __init__(self, client: ClientAdapter, loginman: Loginable):
        super().__init__()
        self.api = qapi.DummyQapi(client, loginman)
        self.like_app = self.api.like_app
        self.bid = -1

    def new_batch(self) -> TY_BID:
        """
        The new_batch function edit internal batch id and return it.

        A batch id can be used to identify a batch, thus even the same feed can have different id e.g. `(bid, uin, abstime)`.

        :rtype: :obj:`.TY_BID`
        :return: The batch_id.
        """

        self.bid += 1
        return self.bid

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, max as 10, defaults to 10

        :raises `qqqr.exception.UserBreak`: qr login canceled
        :raises `aioqzone.exception.LoginError`: not logined
        :raises `SystemExit`: unexcpected error

        :return: feeds num got actually.

        ..note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        got = 0
        aux = None
        for page in range(1000):
            try:
                resp = await self.api.feeds3_html_more(page, count=count - got, aux=aux)
            except (QzoneError, HTTPStatusError) as e:
                log.warning(f"Error when fetching page. Skipped. {e}")
                continue
            aux = resp.aux
            for fd in resp.feeds[: count - got]:
                self._dispatch_feed(fd)
                got += 1
            if not resp.aux.hasMoreFeeds:
                break
            if got >= count:
                break
        return got

    async def get_feeds_by_second(
        self,
        seconds: float,
        start: Optional[float] = None,
        *,
        exceed_pred: Optional[Callable[[FeedRep], Awaitable[bool]]] = None,
    ) -> int:
        """Get feeds by abstime (seconds). Range: `[start - second, start]`.

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.
        :param exceed_pred: another criterion to judge if the feed is out of range, defaults to None

        :raises `qqqr.exception.UserBreak`: qr login canceled
        :raises `aioqzone.exception.LoginError`: not logined
        :raises `SystemExit`: unexcpected error

        :return: feeds num got actually.
        """
        start = start or time.time()
        end = start - seconds
        exceed = got = 0
        aux = None
        for page in range(1000):
            try:
                resp = await self.api.feeds3_html_more(page, aux=aux)
            except (QzoneError, HTTPStatusError) as e:
                log.warning(f"Error when fetching page. Skipped. {e}")
                continue
            aux = resp.aux
            for fd in resp.feeds:
                if fd.abstime > start:
                    continue
                if fd.abstime < end or exceed_pred and await exceed_pred(fd):
                    exceed = True
                    continue
                self._dispatch_feed(fd)
                got += 1
            if not resp.aux.hasMoreFeeds:
                break
            if exceed:
                break
        return got

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
        if feed.uin == 20050606:
            log.info(f"advertisement rule hit: {feed.uin}")
            log.debug(f"Dropped: {feed}")
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, feed))
            return

        if feed.fid.startswith("advertisement"):
            log.info(f"advertisement rule hit: {feed.fid}")
            log.debug(f"Dropped: {feed}")
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, feed))
            return

        model = FeedContent.from_feedrep(feed)
        has_cur = [311]

        try:
            root, htmlinfo = HtmlInfo.from_html(feed.html)
        except ValidationError:
            log.debug("HtmlInfo ValidationError, html=%s", feed.html, exc_info=True)
            self.add_hook_ref("dispatch", self.hook.FeedDropped(self.bid, feed))
            return
        model.set_frominfo(htmlinfo)

        if model.appid in has_cur or model.curkey and model.curkey.startswith("http"):
            # optimize for feeds, no need to parse html content
            return self.__optimize_dispatch(feed, model, htmlinfo, root)
        self.__default_dispatch(feed, model, htmlinfo, root)

    def __optimize_dispatch(self, feed: FeedRep, model: FeedContent, htmlinfo: HtmlInfo, root):
        """Optimized feed processing: request for `emotion_msgdetail` api directly."""

        def detail_procs(dt: Optional[FeedDetailRep]):
            if not dt:
                return self.__default_dispatch(feed, model, htmlinfo, root)

            if dt.pic and any(not i.valid_url() for i in dt.pic):
                return self.__default_dispatch(feed, model, htmlinfo, root)

            model.set_detail(dt)
            add_done_callback(
                (self.add_hook_ref("dispatch", trans_detail(model))),
                lambda t: t and self.add_hook_ref("hook", self.hook.FeedProcEnd(self.bid, model)),
            )

        get_full = self.add_hook_ref("dispatch", self.api.emotion_msgdetail(feed.uin, feed.fid))
        add_done_callback(get_full, detail_procs)

    def __default_dispatch(self, feed: FeedRep, model: FeedContent, htmlinfo: HtmlInfo, root):
        """Default feed processing: Parse info from html feed. If media is detected,
        then request for `floatview_photo_list` album api.
        """
        # has to parse html now
        # TODO: HtmlContent.from_html is risky
        def html_content_procs(htmlct: HtmlContent):
            model.set_fromhtml(htmlct, forward=htmlinfo.unikey)
            self.add_hook_ref("hook", self.hook.FeedProcEnd(self.bid, model))
            self._add_mediaupdate_task(model, htmlct)

        if htmlinfo.complete:
            add_done_callback(
                self.add_hook_ref("dispatch", trans_html(root)),
                lambda root: root is not None
                and html_content_procs(HtmlContent.from_html(root, feed.uin)),
            )
            return

        get_full = self.add_hook_ref(
            "dispatch", self.api.emotion_getcomments(feed.uin, feed.fid, htmlinfo.feedstype)
        )
        cc = lambda f, a: a and f(a)
        add_done_callback(
            get_full,
            lambda full: full
            and add_done_callback(
                self.add_hook_ref("dispatch", trans_html(full)),
                lambda root: root and cc(html_content_procs, HtmlContent.from_html(root)),
            ),
        )

    def _add_mediaupdate_task(self, model: FeedContent, content: HtmlContent) -> None:
        if not (content.album and content.pic):
            return

        async def fv_retry(bid: int, album: AlbumData, num: int):
            assert content.album and content.pic
            for i in range(12):
                st = 2**i - 1
                log.debug(f"sleep {st}s")
                await asyncio.sleep(st)
                try:
                    fv = await self.api.floatview_photo_list(album, num)
                    break
                except QzoneError as e:
                    if e.code == -10001:
                        log.info(f"{str(e)}, retry={i + 1}")
                    else:
                        log.info(f"Error in floatview_photo_list, retry={i + 1}", exc_info=True)
                    continue
                except HTTPStatusError:
                    log.info(f"Error in floatview_photo_list, retry={i + 1}", exc_info=True)
                    continue
                except CorruptError:
                    log.warning(f"Response corrupt!")
                    continue
                except login_exc:
                    return
            else:
                return
            model.media = [VisualMedia.from_picrep(PicRep.from_floatview(i)) for i in fv]
            self.add_hook_ref("hook", self.hook.FeedMediaUpdate(bid, model))

        task = self.add_hook_ref("slowapi", fv_retry(self.bid, content.album, len(content.pic)))
        log.info(f"Media update task registered: {task}")

    async def wait(
        self, *, timeout: Optional[float] = None
    ) -> Tuple[Set[asyncio.Task], Set[asyncio.Task]]:
        """Wait for all dispatch and hook tasks.

        :param timeout: wait timeout, defaults to None
        :return: two set of tasks means (done, pending)

        .. seealso:: :external:meth:`aioqzone.interface.hook.Emittable.wait`
        """

        return await super().wait("dispatch", "hook", timeout=timeout)

    def stop(self) -> None:
        """Clear __all__ registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("FeedApi stopping...")
        if self.hb_timer:
            self.hb_timer.stop()
        super().clear(*self._tasks.keys())

    def clear(self):
        """Cancel all __dispatch__ tasks registered.

        .. seealso:: :external:meth:`aioqzone.interface.hook.Emittable.clear`"""

        super().clear("dispatch")

    def add_heartbeat(self, *, retry: int = 5, retry_intv: float = 5, hb_intv: float = 300):
        """create a heartbeat task and keep a ref of it.

        :param retry: max retry times when some exceptions occurs, defaults to 5.
        :param hb_intv: retry interval, defaults to 5.
        :param hb_intv: heartbeat interval, defaults to 300.
        :return: the heartbeat task
        """

        async def heartbeat_refresh():
            exc, r = None, False
            for i in range(retry):
                try:
                    cnt = (await self.api.get_feeds_count()).friendFeeds_new_cnt
                    log.debug("heartbeat: friendFeeds_new_cnt=%d", cnt)
                    if cnt:
                        self.add_hook_ref("hook", self.hook.HeartbeatRefresh(cnt))
                    return False  # don't stop
                except (
                    QzoneError,
                    HTTPStatusError,
                ) as e:
                    # retry at once
                    exc, excname = e, e.__class__.__name__
                    log.warning("%s captured in heartbeat, retry at once (%d)", excname, i)
                    log.debug(excname, exc_info=e)
                except (
                    HTTPError,
                    SkipLoginInterrupt,
                    UserBreak,
                    asyncio.CancelledError,
                ) as e:
                    # retry in next trigger
                    exc, excname = e, e.__class__.__name__
                    log.warning("%s captured in heartbeat, retry in next trigger", excname)
                    log.debug(excname, exc_info=e)
                    break
                except LoginError as e:
                    if e.strategy != QrStrategy.force:
                        # login error means all methods failed.
                        # we should stop HB if up login will fail.
                        r = True
                    break
                except BaseException as e:
                    exc, r = e, True
                    log.error("Uncaught error in heartbeat.", exc_info=e)
                    break
                await asyncio.sleep(retry_intv)
            else:
                log.error("Max retry exceeds (%d)", retry)

            if r:
                log.warning(f"Heartbeat stopped.")

            self.add_hook_ref("hook", self.hook.HeartbeatFailed(exc))
            return r  # stop at once

        self.hb_timer = AsyncTimer(hb_intv, heartbeat_refresh, delay=hb_intv)
        return self.hb_timer()
