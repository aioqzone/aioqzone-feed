import asyncio

import aioqzone.api as qapi
from aiohttp import ClientSession
from aioqzone.interface.hook import Emittable
from aioqzone.interface.login import Loginable
from aioqzone.type import FeedRep

from ..interface.hook import FeedEvent
from ..type import FeedModel


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
                task.add_done_callback(self.hook.FeedProcEnd)
            got += len(ls)
            if not aux.hasMoreFeeds: break
            if len(ls) >= count: break
        return got

    async def _dispatch_feed(self, bid: int, feed: FeedRep) -> tuple[int, FeedModel]:
        model = FeedModel.from_feedrep(feed)

        def update_detail(detail):
            model.detail = detail

        if model.appid == 311:
            # optimize for 311
            task = asyncio.create_task(self.api.emotion_msgdetail(feed.uin, feed.key))
            task.add_done_callback(lambda t: update_detail(t.result()))
        else:
            raise NotImplementedError
        return bid, model
