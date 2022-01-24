from typing import Optional, Union

from aioqzone.type import FeedDetailRep, FeedRep, PicRep, VideoRep
from pydantic import AnyHttpUrl, BaseModel, HttpUrl


class VisualMedia(BaseModel):
    height: int
    width: int
    thumbnail: HttpUrl
    raw: HttpUrl

    @classmethod
    def from_picrep(cls, pic: PicRep):
        if pic.is_video:
            assert isinstance(pic, VideoRep)
            vi = pic.video_info
            return cls(
                height=vi.cover_height, width=vi.cover_width, thumbnail=vi.url1, raw=vi.url3
            )
        else:
            return cls(height=pic.height, width=pic.width, thumbnail=pic.url1, raw=pic.url3)


class DetailModel(BaseModel):
    content: str = ''
    forward: Optional[Union[AnyHttpUrl, str]] = None
    media: Optional[list[VisualMedia]] = None

    def set_detail(self, obj: FeedDetailRep):
        self.content = obj.content
        self.forward = obj.rt_con and obj.rt_con.content
        if obj.pic is None: self.media = None
        else:
            self.media = [VisualMedia.from_picrep(i) for i in obj.pic]


class FeedModel(BaseModel):
    """FeedModel is a model for storing a feed, with the info to hashing and retrieving the feed."""
    appid: int
    typeid: int
    fid: str    # key
    abstime: int
    uin: int
    nickname: str
    curkey: Optional[Union[HttpUrl, str]] = None
    unikey: Optional[Union[AnyHttpUrl, str]] = None

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
