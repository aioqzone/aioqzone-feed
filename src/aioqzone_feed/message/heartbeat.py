from tylisten import hookdef
from tylisten.futstore import FutureStore

__all__ = ["heartbeat_failed", "heartbeat_refresh", "HeartbeatEmitterMixin"]


@hookdef
def heartbeat_failed(exc: BaseException, stop: bool):
    """
    This message is emitted when the heartbeat got an error.

    :param exc: An exception object that can be used to determine the cause of the heartbeat failure.
    :param stop: Whether the heartbeat is suggested to restart or even stop. One can check :obj:`.exc`
    and make his own decision.
    """


@hookdef
def heartbeat_refresh(num: int):
    """This message is emitted after a heartbeat succeeded and there are new feeds.
    Use this event to wait for all dispatch task to be finished, and send received feeds.

    :param num: number of new feeds"""


class HeartbeatEmitterMixin:
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.hb_failed = heartbeat_failed.new()
        """
        This emitter is triggered when the heartbeat fails because of a exception.
        """
        self.hb_refresh = heartbeat_refresh.new()
        """This emitter is triggered after a heartbeat succeeded and there are new feeds.
        Use this event to wait for all dispatch task to be finished, and send received feeds.
        """
        self.ch_hb = FutureStore()
        """A future store serves as heartbeat channel."""

    def stop(self):
        self.ch_hb.clear()
