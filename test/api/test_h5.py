import asyncio

import pytest
import pytest_asyncio
from aioqzone.api import Loginable
from qqqr.utils.net import ClientAdapter
from tenacity import RetryError

from aioqzone_feed.api import FeedApi

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def api(client: ClientAdapter, man: Loginable):
    api = FeedApi(client, man)
    yield api
    api.stop()


async def test_by_count(api: FeedApi):
    batch = []
    drop = []

    api.feed_processed.add_impl(lambda bid, feed: batch.append(feed))
    api.feed_dropped.add_impl(lambda bid, feed: drop.append(bid))

    try:
        n = await api.get_feeds_by_count(10)
    except RetryError as e:
        pytest.skip(str(e))
    await asyncio.gather(api.ch_feed_dispatch.wait(), api.ch_feed_notify.wait())
    assert len(batch) == n - len(drop)
    assert len(set(batch)) == n - len(drop)


async def test_by_second(api: FeedApi):
    batch = []
    drop = []

    api.feed_processed.add_impl(lambda bid, feed: batch.append(feed))
    api.feed_dropped.add_impl(lambda bid, feed: drop.append(bid))

    try:
        n = await api.get_feeds_by_second(3 * 86400)
    except RetryError as e:
        pytest.skip(str(e))
    await asyncio.gather(api.ch_feed_dispatch.wait(), api.ch_feed_notify.wait())
    assert len(set(batch)) == len(batch)
    assert len(set(batch)) == n - len(drop)
