import asyncio

import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginMan, strategy_to_order
from aioqzone.event import QREvent
from httpx import AsyncClient
from qqqr.event import sub_of
from qqqr.utils.net import ClientAdapter

from . import showqr


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient() as client:
        yield ClientAdapter(client)


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
