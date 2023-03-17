import sys
from unittest.mock import patch

import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.exception import LoginError, QzoneError
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.feed.h5 import FeedH5Api as FeedApi
from aioqzone_feed.event import FeedEvent
from aioqzone_feed.type import FeedContent

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def man(man: MixedLoginMan):
    man.h5()
    return man


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


async def test_exception(api: FeedApi):
    with patch.object(api, "get_active_feeds", side_effect=QzoneError(-3000)), pytest.raises(
        ExceptionGroup, match="max retry exceeds"
    ) as r:
        await api.get_feeds_by_count()
        assert len(r.value.exceptions) == 5

    with patch.object(api, "get_active_feeds", side_effect=QzoneError(-3000)), pytest.raises(
        ExceptionGroup, match="max retry exceeds"
    ) as r:
        await api.get_feeds_by_second(86400)
        assert len(r.value.exceptions) == 5


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
