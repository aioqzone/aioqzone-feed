import asyncio

import aioqzone.api as qapi
from aiohttp import ClientSession
from aioqzone.interface.hook import Emittable
from aioqzone.interface.login import Loginable
from aioqzone.type import FeedRep, FloatViewPhoto, PicRep
from aioqzone.utils.html import HtmlContent, HtmlInfo

from ..interface.hook import FeedEvent
from ..type import FeedContent, VisualMedia


class FeedApi(Emittable):
    hook: FeedEvent

    def __init__(self, sess: ClientSession, loginman: Loginable):
        self.api = qapi.DummyQapi(sess, loginman)

    async def get_feeds_by_count(self, count: int = 10):
        got = 0
        pp = qapi.QzoneApi.FeedsMoreTransaction()
        for i in range(1000):
            ls, aux = await self.api.feeds3_html_more(i, pp, count=count - got)
            for j, v in enumerate(ls):
                task = asyncio.create_task(self._dispatch_feed(got + j, v))
                task.add_done_callback(lambda t: self.hook.FeedProcEnd(*t.result()))
            got += len(ls)
            if not aux.hasMoreFeeds: break
            if len(ls) >= count: break
        return got

    async def _dispatch_feed(self, bid: int, feed: FeedRep) -> tuple[int, FeedContent]:
        model = FeedContent.from_feedrep(feed)
        root, htmlinfo = HtmlInfo.from_html(feed.html)
        model.unikey = htmlinfo.unikey
        model.curkey = htmlinfo.curkey
        has_cur = [311]

        if model.appid in has_cur:
            # optimize for 311
            task = asyncio.create_task(self.api.emotion_msgdetail(feed.uin, feed.key))
            task.add_done_callback(lambda t: model.set_detail(t.result()))

        else:
            if htmlinfo.complete:
                htmlct = HtmlContent.from_html(root)
            else:
                html = await self.api.emotion_getcomments(feed.uin, feed.key, htmlinfo.feedstype)
                htmlct = HtmlContent.from_html(html)

            model.content = htmlct.content
            model.forward = htmlinfo.unikey
            if htmlct.album and htmlct.pic:

                def set_model_pic(fv: list[FloatViewPhoto]):
                    model.media = [VisualMedia.from_picrep(PicRep.from_floatview(i)) for i in fv]
                    asyncio.create_task(self.hook.FeedMediaUpdate(model))

                task = asyncio.create_task(
                    self.api.floatview_photo_list(htmlct.album, len(htmlct.pic))
                )
                task.add_done_callback(lambda fv: set_model_pic(fv.result()))

        return bid, model
