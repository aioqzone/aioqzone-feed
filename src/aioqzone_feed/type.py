from typing import Optional, Union

from aioqzone.type import FeedDetailRep, FeedRep, PicRep, VideoRep
from aioqzone.utils.html import HtmlContent
from aioqzone.utils.time import approx_ts
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


class FeedModel(BaseModel):
    """FeedModel is a model for storing a feed, with the info to hashing and retrieving the feed."""
    appid: int
    typeid: int
    fid: str    # key
    abstime: int
    uin: int
    nickname: str
    curkey: Optional[Union[HttpUrl, str]] = None
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


class DetailModel(BaseModel):
    content: str = ''
    forward: Optional[Union[HttpUrl,
                            FeedModel]] = None    # unikey to the feed, or the content itself.
    media: Optional[list[VisualMedia]] = None

    def set_detail(self, obj: FeedDetailRep, unikey: HttpUrl = None):
        self.content = obj.content
        if obj.rt_uin:
            assert obj.rt_con
            self.forward = FeedContent(
                appid=311,
                typeid=2,
                fid=obj.rt_tid,
                uin=obj.rt_uin,
                nickname=obj.rt_uinname,
                abstime=approx_ts(obj.rt_createTime) if obj.rt_createTime else 0,
                curkey=unikey,
                unikey=unikey,
                content=obj.rt_con.content,
            )
        if obj.pic:
            if self.forward is None:
                self.media = [VisualMedia.from_picrep(i) for i in obj.pic]
            else:
                assert isinstance(self.forward, FeedContent)
                self.forward.media = [VisualMedia.from_picrep(i) for i in obj.pic]

    def set_fromhtml(self, obj: HtmlContent, forward: HttpUrl = None):
        self.content = obj.content
        self.forward = forward
        self.media = [VisualMedia.from_picrep(i) for i in obj.pic] if obj.pic else None


class FeedContent(FeedModel, DetailModel):
    """FeedContent is feed with contents. This might be the common structure to
    rep a feed as it's seen."""
    def __hash__(self) -> int:
        media_hash = hash(tuple(i.raw for i in self.media)) if self.media else 0
        return hash((self.uin, self.abstime, self.content, self.forward, media_hash))
