import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.exception import LoginError
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.feed import FeedApi
from aioqzone_feed.interface.hook import FeedEvent
from aioqzone_feed.type import FeedContent

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def api(client: ClientAdapter, man: MixedLoginMan):
    yield FeedApi(client, man)


class FeedEvent4Test(FeedEvent):
    def __init__(self) -> None:
        super().__init__()
        self.batch = []
        self.drop = []

    async def FeedProcEnd(self, bid: int, feed: FeedContent):
        self.batch.append(feed)
        assert feed.nickname
        assert feed.appid
        assert feed.fid

    async def FeedMediaUpdate(self, feed: FeedContent):
        assert feed.media

    async def FeedDropped(self, bid: int, feed):
        self.drop.append(bid)


async def test_by_count(api: FeedApi):
    hook = FeedEvent4Test()
    api.register_hook(hook)
    try:
        n = await api.get_feeds_by_count(10)
    except LoginError as e:
        pytest.skip(str(e))
    done, pending = await api.wait()
    assert not pending
    assert len(hook.batch) == n - len(hook.drop)
    assert len(set(hook.batch)) == n - len(hook.drop)
    api.clear()
    hook.batch.clear()


async def test_by_second(api: FeedApi):
    hook = FeedEvent4Test()
    api.register_hook(hook)
    try:
        n = await api.get_feeds_by_second(3 * 86400)
    except LoginError as e:
        pytest.skip(str(e))
    done, pending = await api.wait()
    assert not pending
    assert len(set(hook.batch)) == len(hook.batch)
    api.clear()
    hook.batch.clear()
