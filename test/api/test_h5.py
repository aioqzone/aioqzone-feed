import asyncio
import sys
from contextlib import ExitStack
from unittest.mock import patch

import pytest
import pytest_asyncio
from aioqzone.api import UnifiedLoginManager
from aioqzone.exception import LoginError, QzoneError
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.feed.h5 import FeedH5Api as FeedApi

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

pytestmark = pytest.mark.asyncio


async def test_exception(api: FeedApi):
    with ExitStack() as stack:
        stack.enter_context(patch.object(api, "get_active_feeds", side_effect=QzoneError(-3000)))
        r = stack.enter_context(pytest.raises(ExceptionGroup, match="max retry exceeds"))
        await api.get_feeds_by_count()
        assert len(r.value.exceptions) == 5

    with ExitStack() as stack:
        stack.enter_context(patch.object(api, "get_active_feeds", side_effect=QzoneError(-3000)))
        r = stack.enter_context(pytest.raises(ExceptionGroup, match="max retry exceeds"))
        await api.get_feeds_by_second(86400)
        assert len(r.value.exceptions) == 5


@pytest_asyncio.fixture(scope="module")
async def api(client: ClientAdapter, man: UnifiedLoginManager):
    api = FeedApi(client, man, init_hb=False)
    yield api
    api.stop()


async def test_by_count(api: FeedApi):
    batch = []
    drop = []

    api.feed_processed.listeners.append(lambda m: batch.append(m.feed))
    api.feed_dropped.listeners.append(lambda m: drop.append(m.bid))

    try:
        n = await api.get_feeds_by_count(10)
    except LoginError as e:
        pytest.skip(str(e))
    await asyncio.gather(api.ch_dispatch.wait(), api.ch_notify.wait())
    assert len(batch) == n - len(drop)
    assert len(set(batch)) == n - len(drop)


async def test_by_second(api: FeedApi):
    batch = []
    drop = []

    api.feed_processed.listeners.append(lambda m: batch.append(m.feed))
    api.feed_dropped.listeners.append(lambda m: drop.append(m.bid))

    try:
        n = await api.get_feeds_by_second(3 * 86400)
    except LoginError as e:
        pytest.skip(str(e))
    await asyncio.gather(api.ch_dispatch.wait(), api.ch_notify.wait())
    assert len(set(batch)) == len(batch)
    assert len(set(batch)) == n - len(drop)
