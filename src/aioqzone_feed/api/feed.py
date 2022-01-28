import asyncio
from collections import defaultdict
import logging
import time
from typing import Awaitable, Callable

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError
import aioqzone.api as qapi
from aioqzone.exception import LoginError
from aioqzone.exception import QzoneError
from aioqzone.interface.hook import Emittable
from aioqzone.interface.login import Loginable
from aioqzone.type import FeedRep
from aioqzone.type import FloatViewPhoto
from aioqzone.type import PicRep
from aioqzone.utils.html import HtmlContent
from aioqzone.utils.html import HtmlInfo

from ..interface.hook import FeedEvent
from ..type import FeedContent
from ..type import VisualMedia

common_exc = (QzoneError, LoginError, ClientResponseError)
logger = logging.getLogger(__name__)


class FeedApi(Emittable):
    hook: FeedEvent

    def __init__(self, sess: ClientSession, loginman: Loginable):
        self.api = qapi.DummyQapi(sess, loginman)
        self.like_app = self.api.like_app
        self._tasks: defaultdict[str, set[asyncio.Task]] = defaultdict(set)

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, defaults to 10
        :return: feeds num got actually.
        """

        got = 0
        trans = qapi.QzoneApi.FeedsMoreTransaction()
        for page in range(1000):
            ls, aux = await self.api.feeds3_html_more(page, trans, count=count - got)
            for fd in ls[:count - got]:
                task = asyncio.create_task(self._dispatch_feed(got, fd))
                self._tasks['dispatch'].add(task)
                task.add_done_callback(lambda t: self._tasks['dispatch'].remove(t))
                got += 1
            if not aux.hasMoreFeeds: break
            if got >= count: break
        return got

    async def get_feeds_by_second(
        self,
        seconds: int,
        start: float = None,
        exceed_pred: Callable[[FeedRep], Awaitable[bool]] = None
    ) -> int:
        """Get feeds by second spac.

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.
        :param exceed_pred: another pred to judge if the feed is out of range, defaults to None
        :return: feeds num got actually.
        """

        start = start or time.time()
        end = start - seconds
        exceed = got = 0
        trans = qapi.QzoneApi.FeedsMoreTransaction()
        for page in range(1000):
            ls, aux = await self.api.feeds3_html_more(page, trans)
            for fd in ls:
                if fd.abstime > start: continue
                if fd.abstime < end or exceed_pred and await exceed_pred(fd):
                    exceed = True
                    continue
                task = asyncio.create_task(self._dispatch_feed(got, fd))
                self._tasks['dispatch'].add(task)
                task.add_done_callback(lambda t: self._tasks['dispatch'].remove(t))
                got += 1
            if not aux.hasMoreFeeds: break
            if exceed: break
        return got

    async def _dispatch_feed(self, bid: int, feed: FeedRep):
        """dispatch feed according to api support.

        1. Call emotion_msgdetail for supported appid
        2. Else parse html content from response
        3. Full the html by calling emotion_getcomments if it's cutted
        4. Update media by calling floatview_photo_list if html contains thumbnail.

        :param bid: batch id
        :param feed: feed response
        :return: collect these task and wait for them. NOTE: ALWAYS hold a ref to these tasks until they are finished!
        """

        model = FeedContent.from_feedrep(feed)
        root, htmlinfo = HtmlInfo.from_html(feed.html)
        model.unikey = htmlinfo.unikey
        model.curkey = htmlinfo.curkey
        has_cur = [311]

        if model.appid in has_cur or \
           model.curkey and model.curkey.startswith('http'):
            # optimize for feeds
            try:
                detail = await self.api.emotion_msgdetail(feed.uin, feed.key)
            except common_exc:
                logger.error(f'DEBUG: {model}', exc_info=True)
            except:
                logger.fatal(f"Uncaught error! DEBUG: {model}", exc_info=True)
            else:
                model.set_detail(detail)

            task = asyncio.create_task(self.hook.FeedProcEnd(bid, model))
            self._tasks['hook'].add(task)
            task.add_done_callback(lambda t: self._tasks['hook'].remove(t))
            return

        # has to parse html now
        # TODO: HtmlContent.from_html is risky
        if htmlinfo.complete:
            htmlct = HtmlContent.from_html(root, feed.uin)
        else:
            try:
                html = await self.api.emotion_getcomments(feed.uin, feed.key, htmlinfo.feedstype)
            except common_exc:
                logger.error(f'DEBUG: {model}', exc_info=True)
                htmlct = HtmlContent.from_html(root)
            except:
                logger.fatal(f"Uncaught error! DEBUG: {model}", exc_info=True)
                htmlct = HtmlContent.from_html(root)
            else:
                htmlct = HtmlContent.from_html(html)

        model.set_fromhtml(htmlct, forward=htmlinfo.unikey)
        task = asyncio.create_task(self.hook.FeedProcEnd(bid, model))
        self._tasks['hook'].add(task)
        task.add_done_callback(lambda t: self._tasks['hook'].remove(t))

        if htmlct.album and htmlct.pic:
            self._add_mediaupdate_task(model, htmlct)

    def _add_mediaupdate_task(self, model: FeedContent, content: HtmlContent):
        assert content.album and content.pic

        def set_model_pic(fv: list[FloatViewPhoto]):
            model.media = [VisualMedia.from_picrep(PicRep.from_floatview(i)) for i in fv]
            task = asyncio.create_task(self.hook.FeedMediaUpdate(model))
            self._tasks['hook'].add(task)
            task.add_done_callback(lambda t: self._tasks['hook'].remove(t))

        detail = asyncio.create_task(
            self.api.floatview_photo_list(content.album, len(content.pic))
        )
        detail.add_done_callback(lambda fv: set_model_pic(fv.result()))
        self._tasks['slowapi'].add(detail)
        detail.add_done_callback(lambda t: self._tasks['slowapi'].remove(t))

    async def wait(self, *, timeout: float = None):
        """Wait for all dispatchs and hooks.

        :param timeout: timeout as that in :meth:`asyncio.wait`, defaults to None
        :return: two set of tasks, i.e. (done, pending), as that in :meth:`asyncio.wait`
        :rtype: :obj:`tuple[Set[Task], Set[Task]]`
        """

        union = self._tasks['dispatch'].union(self._tasks['hook'])
        if not union: return set(), set()
        return await asyncio.wait(union, timeout=timeout)

    def stop(self):
        """Clear all registered tasks. All tasks will be CANCELLED if not finished.
        """
        self.hb.cancel()
        for s in self._tasks.values():
            while s:
                task: asyncio.Task = s.pop()
                task.cancel()

    def clear(self):
        """Cancel all dispatch tasks registered."""
        s = self._tasks['dispatch']
        while s:
            task: asyncio.Task = s.pop()
            task.cancel()

    def add_heartbeat(self):
        """create a heartbeat task and keep a ref of it.

        :return: the heartbeat task
        :rtype: `Task[None]`
        """
        async def hb_sleep():
            try:
                await self.hook.Heartbeat(await self.api.get_feeds_count())
                await asyncio.sleep(300)
                self.add_heartbeat()    # heartbeat never ends
            except asyncio.CancelledError:
                return

        self.hb = asyncio.create_task(hb_sleep())
        return self.hb
