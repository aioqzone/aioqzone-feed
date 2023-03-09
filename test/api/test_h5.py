import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginMan, strategy_to_order
from aioqzone.event import QREvent
from aioqzone.exception import LoginError
from qqqr.event import sub_of
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.feed.h5 import FeedH5Api as FeedApi
from aioqzone_feed.event import FeedEvent
from aioqzone_feed.type import FeedContent

from . import showqr

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def man(client: ClientAdapter):
    from os import environ as env

    class show_qr_in_test(MixedLoginMan):
        @sub_of(QREvent)
        def _sub_qrevent(self, base):
            class inner_qrevent(QREvent):
                async def QrFetched(self, png: bytes, times: int):
                    showqr(png)

            return inner_qrevent

    man = show_qr_in_test(
        client,
        int(env["TEST_UIN"]),
        strategy_to_order[env.get("TEST_QRSTRATEGY", "forbid")],  # forbid QR by default.
        pwd=env.get("TEST_PASSWORD", None),
        h5=True,
    )

    yield man


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


@pytest_asyncio.fixture(scope="module")
async def api(client: ClientAdapter, man: MixedLoginMan):
    api = FeedApi(client, man, init_hb=False)
    api.register_hook(FeedEvent4Test())
    yield api
    api.stop()


async def test_by_count(api: FeedApi):
    hook = api.hook
    assert isinstance(hook, FeedEvent4Test)
    try:
        n = await api.get_feeds_by_count(10)
    except LoginError as e:
        pytest.skip(str(e))
    done, pending = await api.wait("hook", "dispatch")
    assert not pending
    assert len(hook.batch) == n - len(hook.drop)
    assert len(set(hook.batch)) == n - len(hook.drop)
    api.clear()
    hook.batch.clear()


async def test_by_second(api: FeedApi):
    hook = api.hook
    assert isinstance(hook, FeedEvent4Test)
    try:
        n = await api.get_feeds_by_second(3 * 86400)
    except LoginError as e:
        pytest.skip(str(e))
    done, pending = await api.wait("hook", "dispatch")
    assert not pending
    assert len(set(hook.batch)) == len(hook.batch)
    api.clear()
    hook.batch.clear()
