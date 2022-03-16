import asyncio

import pytest

from aioqzone_feed.utils.task import AsyncTimer

pytestmark = pytest.mark.asyncio


async def test_timer_norm():
    async def inc():
        nonlocal cnt
        if cnt < 4:
            cnt += 1
            return False
        else:
            return True

    cnt = 0
    timer = AsyncTimer(0.1, inc)
    assert timer.state == "INIT"
    timer()
    assert timer.state == "PENDING"
    await asyncio.sleep(1)
    assert timer.state == "FINISHED"
    assert cnt == 4


async def test_timer_exc():
    async def inc():
        nonlocal cnt
        if cnt < 4:
            cnt += 1
            return False
        else:
            raise RuntimeError

    cnt = 0
    timer = AsyncTimer(0.1, inc)
    assert timer.state == "INIT"
    timer()
    assert timer.state == "PENDING"
    await asyncio.sleep(1)
    assert timer.state == "FINISHED"
    assert cnt == 4
