import asyncio
from typing import Type
from unittest import mock

import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.exception import LoginError, QzoneError, SkipLoginInterrupt
from httpx import ConnectError, HTTPError, HTTPStatusError, TimeoutException
from qqqr.event.login import UpEvent
from qqqr.exception import HookError, UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.feed import FeedApi
from aioqzone_feed.interface.hook import FeedEvent
from aioqzone_feed.type import FeedContent

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def api(client: ClientAdapter, man: MixedLoginMan):
    api = FeedApi(client, man)
    yield api
    api.stop()


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


@pytest.mark.parametrize(
    "exc2r,should_alive",
    [
        (LoginError("mock", "allow"), False),
        (SystemExit(), False),
        (LoginError("mock", "force"), True),
        (ConnectError("mock"), True),
        (TimeoutException("mock"), True),
        (HTTPStatusError("mock", request=..., response=...), True),  # type: ignore
        (HTTPError("mock"), True),
        (QzoneError(-3000), True),
        (SkipLoginInterrupt(), True),
        (UserBreak(), True),
        (asyncio.CancelledError(), True),
        (HookError(UpEvent.GetSmsCode), False),
    ],
)
async def test_heartbeat_exc(api: FeedApi, exc2r: Type[BaseException], should_alive: bool):
    api.register_hook(FeedEvent4Test())
    with mock.patch("aioqzone.api.raw.QzoneApi.get_feeds_count", side_effect=exc2r):
        api.add_heartbeat(retry=2, hb_intv=0.1, retry_intv=0)
        assert api.hb_timer
        await asyncio.sleep(0.4)
        assert (api.hb_timer.state == "PENDING") is should_alive
