import asyncio

import aioqzone.api as qapi
from aiohttp import ClientSession
from aioqzone.interface.hook import Emittable
from aioqzone.interface.login import Loginable
from aioqzone.utils.time import dayspac

from ..interface.hook import FeedEvent


class FeedApi(Emittable):
    hook: FeedEvent

    def __init__(self, sess: ClientSession, loginman: Loginable):
        self.api = qapi.DummyQapi(sess, loginman)

    async def get_feeds_by_count(self, count: int = 10):
        got = 0
        pp = qapi.QzoneApi.FeedsMoreTransaction()
        for i in range(1000):
            ls, aux = await self.api.feeds3_html_more(i, pp, count=count - got)
            asyncio.create_task(self.hook.BatchArrive({got + j: v for j, v in enumerate(ls)}))
            got += len(ls)
            if not aux.hasMoreFeeds: break
            if len(ls) >= count: break
        return got
