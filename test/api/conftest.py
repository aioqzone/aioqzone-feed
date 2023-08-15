import asyncio
import io
from contextlib import suppress
from typing import List

import pytest
import pytest_asyncio
from aioqzone.api import QrLoginConfig, UnifiedLoginManager, UpLoginConfig
from aioqzone.message import LoginMethod
from httpx import AsyncClient
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from qqqr.utils.net import ClientAdapter


class test_env(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="test_")
    uin: int = 0
    password: SecretStr = Field(default="")
    order: List[LoginMethod] = ["up"]


@pytest.fixture(scope="session")
def env():
    return test_env()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient() as client:
        yield ClientAdapter(client)


@pytest.fixture(scope="module")
def man(client: ClientAdapter, env: test_env):
    man = UnifiedLoginManager(
        client,
        up_config=UpLoginConfig(uin=env.uin, pwd=env.password),
        qr_config=QrLoginConfig(uin=env.uin),
    )
    man.order = env.order

    with suppress(ImportError):
        from PIL import Image as image

        man.qr_fetched.listeners.append(lambda m: image.open(io.BytesIO(m.png)).show())

    yield man
