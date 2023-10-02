from typing import Type
from unittest.mock import patch

import pytest
import pytest_asyncio
from aioqzone.api import Loginable
from qqqr.exception import UserBreak
from qqqr.utils.net import ClientAdapter
from tenacity import Future, RetryError

from aioqzone_feed.api import FeedApi

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def api(client: ClientAdapter, man: Loginable):
    api = FeedApi(client, man)
    yield api
    api.stop()


@pytest.mark.parametrize(
    "exc2r",
    [
        (SystemExit(),),
        (RetryError(Future.construct(1, UserBreak(), True)),),
    ],
)
async def test_heartbeat_exc(api: FeedApi, exc2r: Type[BaseException]):
    pool = []
    api.hb_failed.add_impl(lambda exc: pool.append(exc))
    with patch.object(api, "mfeeds_get_count", side_effect=exc2r):
        await api.heartbeat_refresh()
        await api.ch_heartbeat_notify.wait()
        assert pool
