import asyncio

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.interface.hook import LoginEvent, QREvent
from aioqzone_feed.api.feed import FeedApi
from aioqzone_feed.interface.hook import FeedEvent
from aioqzone_feed.type import FeedContent

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='module')
async def sess():
    async with ClientSession() as sess:
        yield sess


@pytest_asyncio.fixture(scope='module')
async def man(sess: ClientSession):
    from os import environ as env
    man = MixedLoginMan(
        sess,
        int(env['TEST_UIN']),
        env.get('TEST_QRSTRATEGY', 'forbid'),    # forbid QR by default.
        pwd=env.get('TEST_PASSWORD', None)
    )

    class inner_qrevent(QREvent, LoginEvent):
        async def QrFetched(self, png: bytes):
            showqr(png)

    man.register_hook(inner_qrevent())
    yield man


@pytest_asyncio.fixture(scope='module')
async def api(sess: ClientSession, man: MixedLoginMan):
    yield FeedApi(sess, man)


class FeedEvent4Test(FeedEvent):
    def __init__(self) -> None:
        super().__init__()
        self.batch = []
        self.fs = set()

    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        self.batch.append(bid)
        self.fs.add(feed)
        assert feed.content
        assert feed.appid
        assert feed.fid

    async def FeedMediaUpdate(self, feed: FeedContent):
        assert feed.media


def showqr(png: bytes):
    import cv2 as cv
    import numpy as np

    def frombytes(b: bytes, dtype='uint8', flags=cv.IMREAD_COLOR) -> np.ndarray:
        return cv.imdecode(np.frombuffer(b, dtype=dtype), flags=flags)

    cv.destroyAllWindows()
    cv.imshow('Scan and login', frombytes(png))
    cv.waitKey()


async def test_by_count(api: FeedApi):
    hook = FeedEvent4Test()
    api.register_hook(hook)
    tasks = [task async for task in api.get_feeds_by_count(10)]
    done, pending = await asyncio.wait(tasks, timeout=60)
    assert not pending
    assert [i for i in range(10)] == sorted(hook.batch)
    assert len(hook.batch) == 10
    hook.batch.clear()
