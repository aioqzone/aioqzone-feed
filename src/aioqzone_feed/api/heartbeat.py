import asyncio
import logging
import sys
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

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

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

    async def heartbeat_refresh(self):
        """A wrapper function that calls :obj:`hb_api` and handles all kinds of excpetions
        raised during heartbeat.

        .. note::
            This method calls heartbeat **ONLY ONCE** so it should be called periodically by using
            `.add_heartbeat` or other timer/scheduler.

        .. versionchanged:: 0.13.4

            do not retry, just call heartbeat once

        :return: whether the timer is suggested to be stopped,
            means heartbeat might not success even after a retry, until underlying causes are solved.
        """
        fail = lambda exc: self.add_hook_ref("hook", self.hook.HeartbeatFailed(exc))
        try:
            cnt = new_feed_cnt(await self.hb_api())
            log.debug("heartbeat: new_feed_cnt=%d", cnt)
            if cnt:
                self.add_hook_ref("hook", self.hook.HeartbeatRefresh(cnt))
            return False  # don't stop
        except QzoneError as e:
            fail(e)
            log.warning(e)
            return e.code == -3000
        except HTTPStatusError as e:
            fail(e)
            log.warning(e)
            log.debug(e.request, exc_info=e)
            if e.response.status_code in [403, 302]:
                return True
            return False
        except HookError as e:
            fail(e)
            log.error("HookError in heartbeat, stop at once")
            log.debug(e)
            return True
        except (
            HTTPError,
            SkipLoginInterrupt,
            KeyboardInterrupt,
            UserBreak,
            asyncio.CancelledError,
        ) as e:
            fail(e)
            log.warning(f"{e.__class__.__name__}in heartbeat, retry in next trigger")
            log.debug(e)
            return False
        except LoginError as e:
            fail(e)
            if LoginMethod.up in e.methods_tried:
                # login error means all methods failed.
                # we should stop HB if up login will fail.
                return True
            return False
        except BaseException as e:
            fail(e)
            log.error("Uncaught error in heartbeat.", exc_info=e)
            return True

    def add_heartbeat(
        self,
        *,
        hb_intv: float = 300,
        name: Optional[str] = None,
    ):
        """A helper function that creates a heartbeat task and keep a ref of it.
        A heartbeat task is a timer that circularly calls `.heartbeat_refresh`.

        :param hb_intv: heartbeat interval, defaults to 300.
        :param name: timer name
        :return: the heartbeat task
        """
        heartbeat_refresh = partial(self.heartbeat_refresh)
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
