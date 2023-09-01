from dataclasses import dataclass

from tylisten import BaseMessage, Emitter
from tylisten.futstore import FutureStore

__all__ = ["heartbeat_failed", "heartbeat_refresh", "HeartbeatEmitterMixin"]


@dataclass
class heartbeat_failed(BaseMessage):
    """
    This message is emitted when the heartbeat got an error.
    """

    exc: BaseException
    """An exception object that can be used to determine the cause of the heartbeat failure."""
    stop: bool
    """Whether the heartbeat is suggested to restart or even stop. One can check :obj:`.exc`
    and make his own decision.
    """


@dataclass
class heartbeat_refresh(BaseMessage):
    """This message is emitted after a heartbeat succeeded and there are new feeds.
    Use this event to wait for all dispatch task to be finished, and send received feeds.
    """

    num: int
    """number of new feeds"""


class HeartbeatEmitterMixin:
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.hb_failed = Emitter(heartbeat_failed)
        """
        This emitter is triggered when the heartbeat fails because of a exception.
        """
        self.hb_refresh = Emitter(heartbeat_refresh)
        """This emitter is triggered after a heartbeat succeeded and there are new feeds.
        Use this event to wait for all dispatch task to be finished, and send received feeds.
        """
        self.ch_hb = FutureStore()
        """A future store serves as heartbeat channel."""

    def stop(self):
        self.hb_failed.abort()
        self.hb_refresh.abort()
        self.ch_hb.clear()
