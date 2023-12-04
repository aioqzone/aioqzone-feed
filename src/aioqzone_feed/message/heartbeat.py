from tylisten import hookdef
from tylisten.futstore import FutureStore

__all__ = ["heartbeat_failed", "heartbeat_refresh", "HeartbeatEmitterMixin"]


@hookdef
def heartbeat_failed(exc: BaseException):
    """
    This message is emitted when the heartbeat got an error.

    :param exc: An exception object that can be used to determine the cause of the heartbeat failure.

    .. hint::

        - :external+aioqzone:exc:`QzoneError`(code=-3000): Login expired. Relogin is needed.
        - :external+aiohttp:exc:`ClientResponseError`(status=500): Qzone server buzy. Ignore it.
    """


@hookdef
def heartbeat_refresh(num: int):
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
        self.ch_heartbeat_notify.clear()
