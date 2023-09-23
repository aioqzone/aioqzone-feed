import asyncio
import logging
from functools import singledispatch
from typing import Optional, Union

from aioqzone.api.h5 import QzoneH5API
from aioqzone.api.web import QzoneWebAPI
from aioqzone.exception import LoginError, QzoneError, SkipLoginInterrupt
from aioqzone.model import FeedCount as H5FeedsCount
from aioqzone.model.response.web import FeedsCount as WebFeedsCount
from httpx import HTTPError, HTTPStatusError
from qqqr.exception import UserBreak

from aioqzone_feed.message import HeartbeatEmitterMixin

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


class HeartbeatApi(HeartbeatEmitterMixin):
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
        """

        fail = (
            lambda exc, stopped: self.ch_hb.add_awaitable(self.hb_failed.results(exc, stopped))
            and None
        )
        try:
            cnt = new_feed_cnt(await self.hb_api())
            log.debug("heartbeat: new_feed_cnt=%d", cnt)
            if cnt:
                self.ch_hb.add_awaitable(self.hb_refresh.results(cnt))
            return
        except QzoneError as e:
            log.warning(e)
            return fail(e, e.code == -3000)
        except LoginError as e:
            log.warning("心跳出现登陆错误")
            return fail(e, "up" in e.methods_tried)
        except HTTPStatusError as e:
            log.warning(e)
            log.debug(e.request, exc_info=e)
            return fail(e, e.response.status_code in [403, 302])
        except (
            HTTPError,
            SkipLoginInterrupt,
            KeyboardInterrupt,
            UserBreak,
            asyncio.CancelledError,
        ) as e:
            log.warning(f"{e.__class__.__name__}in heartbeat, retry in next trigger")
            log.debug(e)
            return fail(e, False)

        except BaseException as e:
            log.error("Uncaught error in heartbeat.", exc_info=e)
            return fail(e, True)

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("HeartbeatApi stopping...")
        super().stop()
