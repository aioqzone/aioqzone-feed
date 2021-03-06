import asyncio

import pytest
import pytest_asyncio
from aioqzone.api.loginman import MixedLoginEvent, MixedLoginMan, QrStrategy
from httpx import AsyncClient
from qqqr.ssl import ssl_context
from qqqr.utils.net import ClientAdapter

from . import showqr


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient(verify=ssl_context()) as client:
        yield ClientAdapter(client)


@pytest_asyncio.fixture(scope="module")
async def man(client: ClientAdapter):
    from os import environ as env

    man = MixedLoginMan(
        client,
        int(env["TEST_UIN"]),
        QrStrategy[env.get("TEST_QRSTRATEGY", "forbid")],  # forbid QR by default.
        pwd=env.get("TEST_PASSWORD", None),
    )

    class inner_qrevent(MixedLoginEvent):
        def __init__(self) -> None:
            self._cancel_flag = asyncio.Event()
            self._refresh_flag = asyncio.Event()

        async def QrFetched(self, png: bytes, times: int):
            showqr(png)

        @property
        def cancel_flag(self) -> asyncio.Event:
            return self._cancel_flag

        @property
        def refresh_flag(self) -> asyncio.Event:
            return self._refresh_flag

    man.register_hook(inner_qrevent())
    yield man
