from typing import Optional, Union

from aioqzone.type import FeedDetailRep, FeedRep, PicRep, VideoRep, LikeData
from pydantic import BaseModel, HttpUrl


class DetailModel(BaseModel):
    content: str = ''
    forward: Optional[Union[HttpUrl, str]] = None
    pic: Optional[list[Union[PicRep, VideoRep]]] = None

    @classmethod
    def from_detailrep(cls, obj: FeedDetailRep):
        return cls(content=obj.content, forward=obj.rt_con and obj.rt_con.content, pic=obj.pic)


class FeedModel(BaseModel):
    """FeedModel is a model for storing a feed, with the info to hashing and retrieving the feed."""
    appid: int
    typeid: int
    fid: str    # key
    abstime: int
    uin: int
    nickname: str
    curkey: Optional[str] = None
    unikey: Optional[Union[HttpUrl, str]] = None

    def __hash__(self) -> int:
        return hash((self.uin, self.abstime))

    @classmethod
    def from_feedrep(cls, obj: FeedRep, **kwds):
        return cls(
            appid=obj.appid,
            typeid=obj.typeid,
            fid=obj.key,
            abstime=obj.abstime,
            uin=obj.uin,
            nickname=obj.nickname,
            **kwds
        )


class FeedContent(FeedModel, DetailModel):
    """FeedContent is feed with contents. This might be the common structure to
    rep a feed as it's seen."""
    pass
