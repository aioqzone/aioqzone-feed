from typing import Optional, Union

from aioqzone.type import FeedDetailRep
from aioqzone.type import FeedRep
from aioqzone.type import LikeData
from aioqzone.type import PicRep
from aioqzone.type import VideoRep
from aioqzone.utils.html import HtmlContent
from aioqzone.utils.html import HtmlInfo
from aioqzone.utils.time import approx_ts
from pydantic import BaseModel
from pydantic import HttpUrl


class VisualMedia(BaseModel):
    height: int
    width: int
    thumbnail: HttpUrl
    raw: HttpUrl
    is_video: bool

    @classmethod
    def from_picrep(cls, pic: PicRep):
        if pic.is_video:
            assert isinstance(pic, VideoRep)
            vi = pic.video_info
            return cls(
                height=vi.cover_height,
                width=vi.cover_width,
                thumbnail=vi.thumb,
                raw=vi.raw,
                is_video=True
            )
        else:
            return cls(
                height=pic.height,
                width=pic.width,
                thumbnail=pic.url1,
                raw=pic.url3,
                is_video=False
            )


class BaseFeed(BaseModel):
    """FeedModel is a model for storing a feed, with the info to hashing and retrieving the feed."""
    appid: int
    typeid: int
    fid: str
    """Feed id, a hex string with 24/32 chars, or a much shorter placeholder.

    .. note::
        fid is not a enough identifier for ANY feed. For comman feed that appid==311, it is
        a 24 or 32 length hex string, which might be satisfied. But for shares that appid!=311, it is a
        short string and is commonly used by multiple shares. So do not distinguish all feeds on this field."""
    abstime: int
    """Feed created time. common alias: `created_time`"""
    uin: int
    nickname: str
    curkey: Optional[Union[HttpUrl, str]] = None
    """The identifier to this feed. May be a url, or just a identifier string."""
    unikey: Optional[Union[HttpUrl, str]] = None
    """The identifier to the original content. May be a url in all kinds
    (sometimes not strictly in a correct format, but it is from the meaning)"""
    class Config:
        orm_mode = True

    def __hash__(self) -> int:
        return hash((self.uin, self.abstime))

    @classmethod
    def from_feedrep(cls, obj: FeedRep, **kwds):
        return cls(
            appid=obj.appid,
            typeid=obj.typeid,
            fid=obj.fid,
            abstime=obj.abstime,
            uin=obj.uin,
            nickname=obj.nickname,
            **kwds
        )


class BaseDetail(BaseModel):
    content: str = ''
    forward: Optional[Union[HttpUrl, str,
                            BaseFeed]] = None    # unikey to the feed, or the content itself.
    media: Optional[list[VisualMedia]] = None

    def set_detail(self, obj: FeedDetailRep):
        self.content = obj.content
        if obj.rt_uin:
            assert obj.rt_con
            unikey = LikeData.persudo_unikey(311, obj.rt_uin, fid=obj.rt_tid)
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

    def set_fromhtml(self, obj: HtmlContent, forward: Union[HttpUrl, str] = None):
        self.content = obj.content
        self.forward = forward
        self.media = [VisualMedia.from_picrep(i) for i in obj.pic] if obj.pic else None


class FeedContent(BaseFeed, BaseDetail):
    """FeedContent is feed with contents. This might be the common structure to
    represent a feed as what it's known."""
    islike: Optional[int] = 0

    def __hash__(self) -> int:
        media_hash = hash(tuple(i.raw for i in self.media)) if self.media else 0
        return hash((self.uin, self.abstime, self.content, self.forward, media_hash))

    def set_detail(self, info: HtmlInfo, obj: FeedDetailRep):
        self.curkey = info.curkey
        self.unikey = info.unikey
        self.islike = info.islike
        return super().set_detail(obj)

    def set_fromhtml(self, info: HtmlInfo, obj: HtmlContent, forward: Union[HttpUrl, str] = None):
        self.curkey = info.curkey
        self.unikey = info.unikey
        self.islike = info.islike
        return super().set_fromhtml(obj, forward)
