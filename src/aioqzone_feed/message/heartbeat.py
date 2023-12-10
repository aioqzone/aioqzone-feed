import typing as t

from tylisten import hookdef
from tylisten.futstore import FutureStore

__all__ = ["heartbeat_failed", "heartbeat_refresh", "HeartbeatEmitterMixin"]


@hookdef
def heartbeat_failed(exc: BaseException) -> t.Any:
    """
    This message is emitted when the heartbeat got an error.

    :param exc: An exception object that can be used to determine the cause of the heartbeat failure.

    .. hint::

        Recommended handling strategy:

        - :exc:`~aioqzone.exception.QzoneError` if :obj:`~aioqzone.exception.QzoneError.code` = -3000: Login expired. Relogin is needed.
        - :exc:`~aiohttp.ServerTimeoutError` / :exc:`~aiohttp.ClientResponseError` if :obj:`~aiohttp.ClientResponseError.status` = 500: Qzone server buzy. Ignore it.
    """


@hookdef
def heartbeat_refresh(num: int) -> t.Any:
    """This message is emitted after a heartbeat succeeded and there are new feeds.
    Use this event to wait for all dispatch task to be finished, and send received feeds.

    :param num: number of new feeds"""


class HeartbeatEmitterMixin:
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.hb_failed = heartbeat_failed()
        """
        This emitter is triggered when the heartbeat fails because of a exception.
        """
        self.hb_refresh = heartbeat_refresh()
        """This emitter is triggered after a heartbeat succeeded and there are new feeds.
        Use this event to wait for all dispatch task to be finished, and send received feeds.
        """
        self.ch_heartbeat_notify = FutureStore()
        """A future store serves as heartbeat channel."""

    def stop(self):
        """Clear future stores."""
        self.ch_heartbeat_notify.clear()
