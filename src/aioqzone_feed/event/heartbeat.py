from typing import Optional

from qqqr.event import Event


class HeartbeatEvent(Event):
    async def HeartbeatFailed(self, exc: Optional[BaseException] = None):
        """
        The HeartbeatFailed function is called when the heartbeat fails.
        It can be used to log an error and call :meth:`aioqzone_feed.api.feed.FeedApi.add_heartbeat`
        again if possible.

        :param exc: Used to pass an exception object that can be used to determine the cause of the heartbeat failure.
        """

        pass

    async def HeartbeatRefresh(self, num: int):
        """This event is triggered after a heartbeat succeeded and there are new feeds.
        Use this event to wait for all dispatch task to be finished, and send received feeds.

        :param num: number of new feeds

        Example:

        .. code-block:: python

            async def HeartbeatRefresh(self, num: int):
                await api.get_feeds_by_count(num)
                await api.wait()        # wait for all dispatch tasks and hook tasks
                await queue.send_all()  # send received feeds
        """
        pass
