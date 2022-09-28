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
    assert timer.last_call == 0
    timer()
    assert timer.state == "PENDING"
    await asyncio.sleep(1)
    assert timer.state == "FINISHED"
    assert timer.last_call > 0
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
    assert timer.last_call == 0
    await asyncio.sleep(1)
    assert timer.state == "FINISHED"
    assert timer.last_call > 0
    assert cnt == 4


async def test_timer_restart():
    async def inc():
        nonlocal cnt, entr
        if cnt < 4:
            cnt += 1
            return False
        else:
            entr += 1
            raise RuntimeError

    entr = 0
    timer = AsyncTimer(0.1, inc)
    assert timer.state == "INIT"
    for _ in range(2):
        cnt = 0
        timer()
        assert timer.state == "PENDING"
        await asyncio.sleep(1)
        assert timer.state == "FINISHED"
        assert cnt == 4
    assert entr == 2


async def test_timer_reschedule():
    async def inc():
        nonlocal cnt, timer
        if cnt == 0:
            cnt += 1
            timer.change_interval(0.5)
            return False
        else:
            return True

    cnt = 0
    timer = AsyncTimer(0.1, inc)
    timer()
    assert timer.state == "PENDING"
    await asyncio.sleep(1)
    assert timer.state == "FINISHED"
    assert cnt == 1
    assert timer.delay > 0.4
