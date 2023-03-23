import asyncio
import logging
from functools import partial, singledispatch
from typing import Optional, Union

from aioqzone.api import QzoneWebAPI
from aioqzone.api.h5 import QzoneH5API
from aioqzone.event import LoginMethod
from aioqzone.exception import LoginError, QzoneError, SkipLoginInterrupt
from aioqzone.type.resp import FeedsCount as WebFeedsCount
from aioqzone.type.resp.h5 import FeedCount as H5FeedsCount
from httpx import HTTPError, HTTPStatusError
from qqqr.event import Emittable
from qqqr.exception import HookError, UserBreak

from aioqzone_feed.event import HeartbeatEvent
from aioqzone_feed.utils.task import AsyncTimer

log = logging.getLogger(__name__)


@singledispatch
def new_feed_cnt(result) -> int:
    raise TypeError(result, type(result))


@new_feed_cnt.register
def _friendFeeds_new_cnt(result: WebFeedsCount):
    return result.friendFeeds_new_cnt


@new_feed_cnt.register
def _active_cnt(result: H5FeedsCount):
    return result.active_cnt


class HeartbeatApi(Emittable[HeartbeatEvent]):
    hb_timer = None

    def __init__(self, api: Union[QzoneH5API, QzoneWebAPI]) -> None:
        super().__init__()
        if isinstance(api, QzoneH5API):
            self.hb_api = api.mfeeds_get_count
        elif isinstance(api, QzoneWebAPI):
            self.hb_api = api.get_feeds_count
        else:
            raise TypeError("wrong api instance:", type(api))

    async def heartbeat_refresh(self, *, retry: int = 2, retry_intv: float = 5):
        """A wrapper function that calls :external:meth:`aioqzone.api.QzoneWebAPI.get_feeds_count`
        and handles all kinds of excpetions raised during heartbeat.

        .. note::
            This method calls heartbeat **ONLY ONCE** so it should be called circularly by using
            `.add_heartbeat` or other timer/scheduler.

        :param retry: retry times on QzoneError, default as 2.
        :param retry_intv: retry interval on QzoneError
        :return: whether the timer should stop, means heartbeat will always fail until something is changed.
        """
        exc = last_fail_hook = None
        r = False
        for i in range(retry):
            try:
                cnt = new_feed_cnt(await self.hb_api())
                log.debug("heartbeat: new_feed_cnt=%d", cnt)
                if cnt:
                    self.add_hook_ref("hook", self.hook.HeartbeatRefresh(cnt))
                return False  # don't stop
            except (
                QzoneError,
                HTTPStatusError,
            ) as e:
                # retry at once
                exc, excname = e, e.__class__.__name__
                log.warning("%s captured in heartbeat, retry at once (%d)", excname, i)
                log.debug(excname, exc_info=e)
            except HookError as e:
                if e.hook.__qualname__ == last_fail_hook:
                    # if the same hook raises exception twice, we assume it is systematically broken
                    # so we should stop heartbeat at once.
                    r = True
                    break
                last_fail_hook = e.hook.__qualname__
                log.error("HookError captured in heartbeat, retry at once (%d)", i)
            except (
                HTTPError,
                SkipLoginInterrupt,
                KeyboardInterrupt,
                UserBreak,
                asyncio.CancelledError,
            ) as e:
                # retry in next trigger
                exc, excname = e, e.__class__.__name__
                log.warning("%s captured in heartbeat, retry in next trigger", excname)
                log.debug(excname, exc_info=e)
                break
            except LoginError as e:
                if LoginMethod.up in e.methods_tried:
                    # login error means all methods failed.
                    # we should stop HB if up login will fail.
                    r = True
                break
            except BaseException as e:
                exc, r = e, True
                log.error("Uncaught error in heartbeat.", exc_info=e)
                break
            await asyncio.sleep(retry_intv)
        else:
            log.error("Max retry exceeds (%d)", retry)

        if r:
            log.warning(f"Heartbeat stopped.")

        self.add_hook_ref("hook", self.hook.HeartbeatFailed(exc))
        return r  # stop at once

    def add_heartbeat(
        self,
        *,
        retry: int = 5,
        retry_intv: float = 5,
        hb_intv: float = 300,
        name: Optional[str] = None,
    ):
        """A helper function that creates a heartbeat task and keep a ref of it.
        A heartbeat task is a timer that circularly calls `.heartbeat_refresh`.

        :param retry: max retry times when some exceptions occurs, defaults to 5.
        :param hb_intv: retry interval, defaults to 5.
        :param hb_intv: heartbeat interval, defaults to 300.
        :param name: timer name
        :return: the heartbeat task
        """
        heartbeat_refresh = partial(self.heartbeat_refresh, retry=retry, retry_intv=retry_intv)
        self.hb_timer = AsyncTimer(
            hb_intv, heartbeat_refresh, delay=hb_intv, name=name or "heartbeat"
        )
        return self.hb_timer()

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("HeartbeatApi stopping...")
        if self.hb_timer:
            self.hb_timer.stop()
        self.clear(*self._tasks.keys())
