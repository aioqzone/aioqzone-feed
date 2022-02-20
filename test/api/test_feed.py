import asyncio

from aiohttp import ClientSession
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.interface.hook import LoginEvent
from aioqzone.interface.hook import QREvent
import pytest
import pytest_asyncio

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
    from qzemoji import init
    await init()
    yield FeedApi(sess, man)


class FeedEvent4Test(FeedEvent):
    def __init__(self) -> None:
        super().__init__()
        self.batch = {}

    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        self.batch[bid] = feed
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
    n = await api.get_feeds_by_count(10)
    done, pending = await api.wait()
    assert not pending
    assert len(hook.batch) == n
    assert len(set(hook.batch.values())) == n
    assert all(i.exception() is None for i in done)
    api.clear()
    hook.batch.clear()


async def test_by_second(api: FeedApi):
    hook = FeedEvent4Test()
    api.register_hook(hook)
    n = await api.get_feeds_by_second(3 * 86400)
    done, pending = await api.wait()
    assert not pending
    assert [i for i in range(len(hook.batch))] == sorted(hook.batch)
    assert len(set(hook.batch.values())) == len(hook.batch)
    assert all(i.exception() is None for i in done)
    api.clear()
    hook.batch.clear()
