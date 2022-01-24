import asyncio

import pytest
from aiohttp import ClientSession
from aioqzone.api.loginman import MixedLoginMan
from qzone2tg.api.feed import FeedApi
from qzone2tg.interface.hook import FeedEvent
from qzone2tg.type import FeedContent

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
async def sess():
    async with ClientSession() as sess:
        yield sess


@pytest.fixture(scope='module')
async def man(sess: ClientSession):
    from os import environ as env
    yield MixedLoginMan(
        sess,
        int(env['TEST_UIN']),
        env.get('TEST_QRSTRATEGY', 'forbid'),    # forbid QR by default.
        pwd=env.get('TEST_PASSWORD', None)
    )


@pytest.fixture(scope='module')
async def api(sess: ClientSession, man: MixedLoginMan):
    a = FeedApi(sess, man)
    a.hook = FeedEvent4Test()
    yield a


class FeedEvent4Test(FeedEvent):
    def FeedProcEnd(self, bid: int, feed: FeedContent):
        assert feed.content
        assert feed.appid
        assert feed.fid

    def FeedMediaUpdate(self, feed: FeedContent):
        assert feed.media


async def test_by_count(api: FeedApi):
    assert 10 == await api.get_feeds_by_count()
