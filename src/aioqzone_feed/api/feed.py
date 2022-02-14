import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError
import aioqzone.api as qapi
from aioqzone.exception import CorruptError
from aioqzone.exception import LoginError
from aioqzone.exception import QzoneError
from aioqzone.interface.hook import Emittable
from aioqzone.interface.login import Loginable
from aioqzone.type import AlbumData
from aioqzone.type import FeedRep
from aioqzone.type import LikeData
from aioqzone.type import PicRep
from aioqzone.utils.html import HtmlContent
from aioqzone.utils.html import HtmlInfo
from qqqr.exception import UserBreak

from ..interface.hook import FeedEvent
from ..type import FeedContent
from ..type import VisualMedia

logger = logging.getLogger(__name__)
qz_exc = (QzoneError, ClientResponseError)
login_exc = (LoginError, UserBreak, asyncio.CancelledError)

T = TypeVar('T')


def add_done_callback(task: asyncio.Task[T], cb: Callable[[Optional[T]], Any]):
    def safe_unpack(task: asyncio.Task[T]):
        try:
            return task.result()
        except qz_exc:
            logger.error(f'DEBUG: {task}', exc_info=True)
        except LoginError as e:
            logger.error(f'LoginError: {e}')
            raise e
        except UserBreak as e:
            logger.info('UserBreak captured!')
            raise e
        except SystemExit as e:
            raise e
        except RuntimeError as e:
            if e.args[0] == 'Session is closed':
                logger.error(f'DEBUG: {task}', exc_info=True)
            else:
                raise e
        except:
            logger.fatal('Uncaught Exception!', exc_info=True)
            from sys import exit
            exit(1)

    task.add_done_callback(lambda t: cb(safe_unpack(t)))
    return task


class FeedApi(Emittable[FeedEvent]):
    def __init__(self, sess: ClientSession, loginman: Loginable):
        super().__init__()
        self.api = qapi.DummyQapi(sess, loginman)
        self.like_app = self.api.like_app

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, defaults to 10

        :raises `qqqr.exception.UserBreak`: qr login canceled
        :raises `aioqzone.exception.LoginError`: not logined
        :raises `SystemExit`: unexcpected error

        :return: feeds num got actually.
        """

        got = 0
        trans = qapi.QzoneApi.FeedsMoreTransaction()
        for page in range(1000):
            try:
                ls, aux = await self.api.feeds3_html_more(page, trans, count=count - got)
            except qz_exc as e:
                logger.warning(f'Error when fetching page. Skipped. {e}')
                continue
            for fd in ls[:count - got]:
                self._dispatch_feed(got, fd)
                got += 1
            if not aux.hasMoreFeeds: break
            if got >= count: break
        return got

    async def get_feeds_by_second(
        self,
        seconds: int,
        start: float = None,
        *,
        exceed_pred: Callable[[FeedRep], Awaitable[bool]] = None
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
        trans = qapi.QzoneApi.FeedsMoreTransaction()
        for page in range(1000):
            try:
                ls, aux = await self.api.feeds3_html_more(page, trans)
            except qz_exc as e:
                logger.warning(f'Error when fetching page. Skipped. {e}')
                continue
            for fd in ls:
                if fd.abstime > start: continue
                if fd.abstime < end or exceed_pred and await exceed_pred(fd):
                    exceed = True
                    continue
                self._dispatch_feed(got, fd)
                got += 1
            if not aux.hasMoreFeeds: break
            if exceed: break
        return got

    def _dispatch_feed(self, bid: int, feed: FeedRep) -> None:
        """dispatch feed according to api support.

        1. Call emotion_msgdetail for supported appid
        2. Else parse html content from response
        3. Full the html by calling emotion_getcomments if it's cutted
        4. Update media by calling floatview_photo_list if html contains thumbnail.

        All api that must be scheduled during this batch transaction must be added into
        `dispatch` task set. Other api which can be called later or has low-priority should
        be added into `slowapi` set.

        :param bid: batch id
        :param feed: feed
        """

        if feed.fid.startswith('advertisement'):
            logger.info(f"advertisement rule hit: {feed}")
            self.add_hook_ref('dispatch', self.hook.FeedDropped(bid, feed))
            return

        model = FeedContent.from_feedrep(feed)
        root, htmlinfo = HtmlInfo.from_html(feed.html)
        has_cur = [311]

        if model.appid in has_cur or \
           model.curkey and model.curkey.startswith('http'):
            # optimize for feeds, no need to parse html content
            detail = self.add_hook_ref('dispatch', self.api.emotion_msgdetail(feed.uin, feed.fid))
            add_done_callback(detail, lambda dt: dt and \
                (model.set_detail(htmlinfo, dt) or \
                    self.add_hook_ref('hook', self.hook.FeedProcEnd(bid, model)))
            )
            return

        # has to parse html now
        # TODO: HtmlContent.from_html is risky
        def html_content_procs(htmlct: HtmlContent):
            model.set_fromhtml(htmlinfo, htmlct, forward=htmlinfo.unikey)
            self.add_hook_ref('hook', self.hook.FeedProcEnd(bid, model))
            self._add_mediaupdate_task(model, htmlct)

        if htmlinfo.complete:
            htmlct = HtmlContent.from_html(root, feed.uin)
            html_content_procs(htmlct)
        else:
            detail = self.add_hook_ref(
                'dispatch', self.api.emotion_getcomments(feed.uin, feed.fid, htmlinfo.feedstype)
            )
            add_done_callback(detail, lambda dt: dt and \
                (htmlct := HtmlContent.from_html(dt)) and \
                html_content_procs(htmlct)
            )

    def _add_mediaupdate_task(self, model: FeedContent, content: HtmlContent) -> None:
        if not (content.album and content.pic): return

        async def fv_retry(album: AlbumData, num: int):
            assert content.album and content.pic
            for i in range(12):
                try:
                    fv = await self.api.floatview_photo_list(album, num)
                    break
                except qz_exc:
                    logger.info(f'Error in floatview_photo_list, retry={i + 1}', exc_info=True)
                    continue
                except CorruptError:
                    logger.warning(f'Response corrupt!')
                    continue
                except login_exc:
                    return
            else:
                return
            model.media = [VisualMedia.from_picrep(PicRep.from_floatview(i)) for i in fv]
            self.add_hook_ref('hook', self.hook.FeedMediaUpdate(model))

        task = self.add_hook_ref('slowapi', fv_retry(content.album, len(content.pic)))
        logger.info(f'Media update task registered: {task}')

    async def wait(self, *, timeout: float = None) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
        """Wait for all dispatch and hook tasks.

        :param timeout: wait timeout, defaults to None
        :return: two set of tasks means (done, pending)

        .. seealso:: :external:meth:`aioqzone.interface.hook.Emittable.wait`
        """

        return await super().wait('dispatch', 'hook', timeout=timeout)

    def stop(self) -> None:
        """Clear all registered tasks. All tasks will be CANCELLED if not finished.
        """

        self.hb.cancel()
        super().clear(*self._tasks.keys())

    def clear(self):
        """Cancel all dispatch tasks registered.

        .. seealso:: :external:meth:`aioqzone.interface.hook.Emittable.clear`"""

        super().clear('dispatch')

    def add_heartbeat(self, retry: int = 5) -> asyncio.Task[None]:
        """create a heartbeat task and keep a ref of it.

        :param retry: max retry times when exception occurs, defaults to 5.
        :return: the heartbeat task
        """
        async def hb_loop():
            i = 0
            while i < retry:
                try:
                    await asyncio.sleep(300)
                    count = await self.api.get_feeds_count()
                except qz_exc:
                    i += 1
                    logger.warning('Error when heartbeat. retry=%d', i, exc_info=True)
                    continue
                except login_exc as e:
                    logger.info(f'Heartbeat stopped: {e}')
                    return

                i = 0
                self.add_hook_ref('dispatch', self.get_feeds_by_count(count.friendFeeds_new_cnt))
                self.add_hook_ref('hook', self.hook.Heartbeat(count))

            logger.error('Max retry exceeds. Heartbeat stopped.')

        self.hb = asyncio.create_task(hb_loop())
        return self.hb
