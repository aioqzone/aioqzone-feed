import sys
from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import List, Optional, Union

from aioqzone.type.entity import ConEntity
from aioqzone.type.internal import LikeData
from aioqzone.type.resp import FeedDetailRep, FeedRep, PicRep, VideoInfo, VideoRep
from aioqzone.type.resp.h5 import FeedData, FeedOriginal, FeedVideo, PicData, Share
from aioqzone.utils.entity import split_entities
from aioqzone.utils.html import HtmlContent, HtmlInfo
from aioqzone.utils.time import approx_ts
from typing_extensions import Self

if sys.version_info < (3, 9):
    # python 3.8 patch for singledispatchmethod
    # https://github.com/python/cpython/issues/83860
    # workaround: https://github.com/python/cpython/issues/83860#issuecomment-1093857837

    def _register(self, cls, method=None):
        if hasattr(cls, "__func__"):
            setattr(cls, "__annotations__", cls.__func__.__annotations__)
        return self.dispatcher.register(cls, func=method)

    singledispatchmethod.register = _register


@dataclass
class VisualMedia:
    height: int
    width: int
    raw: str
    is_video: bool
    thumbnail: Optional[str] = None

    @singledispatchmethod
    def from_pic(cls, pic):
        raise TypeError(pic)

    @from_pic.register
    @classmethod
    def _(cls, pic: PicRep):
        if pic.is_video:
            assert isinstance(pic, VideoRep)
            return cls.from_video(pic.video_info)
        else:
            return cls(
                height=pic.height,
                width=pic.width,
                thumbnail=pic.thumb,
                raw=pic.raw,
                is_video=False,
            )

    @from_pic.register
    @classmethod
    def _(cls, pic: PicData):
        if pic.videodata:
            return cls.from_video(pic.videodata)

        raw = pic.photourl.largest
        thumb = pic.photourl.smallest
        return cls(
            is_video=False,
            height=pic.origin_height,
            width=pic.origin_width,
            raw=raw.url,
            thumbnail=thumb.url,
        )

    @singledispatchmethod
    @classmethod
    def from_video(cls, video):
        raise TypeError(video)

    @from_video.register
    @classmethod
    def _(cls, video: VideoInfo):
        return cls(
            height=video.cover_height,
            width=video.cover_width,
            thumbnail=video.thumb,
            raw=video.raw,
            is_video=True,
        )

    @from_video.register
    @classmethod
    def _(cls, video: FeedVideo):
        cover = video.coverurl.largest
        return cls(
            height=cover.height,
            width=cover.width,
            thumbnail=cover.url,
            raw=video.videourl,
            is_video=True,
        )


@dataclass
class BaseFeed:
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
    """Feed owner uin. (hostuin)"""
    nickname: str
    """Feed owner nickname."""
    curkey: Optional[str] = None
    """The identifier to this feed. May be a url, or just a identifier string."""
    unikey: Optional[str] = None
    """The identifier to the original content. May be a url in all kinds
    (sometimes not strictly in a correct format, but it is from the meaning)"""
    topicId: str = ""
    """This is used to reply to this feed, or can be used to update this feed
    if current user own this feed.

    .. versionadded:: 0.9.2a1
    """
    islike: bool = False

    def __hash__(self) -> int:
        return hash((self.uin, self.abstime))

    def __le__(self, o: "BaseFeed"):
        if self.abstime > o.abstime:
            return False
        if self.abstime < o.abstime:
            return True
        if self.uin > o.uin:
            return False
        return True

    def __lt__(self, o: "BaseFeed"):
        if self.abstime < o.abstime:
            return True
        if self.abstime > o.abstime:
            return False
        if self.uin < o.uin:
            return True
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(uin={self.uin},abstime={self.abstime}')"

    @singledispatchmethod
    @classmethod
    def from_feed(cls, obj, **kwds) -> Self:
        raise TypeError(obj)

    @from_feed.register
    @classmethod
    def _(cls, obj: FeedRep, **kwds):
        return cls(
            appid=obj.appid,
            typeid=obj.typeid,
            fid=obj.fid,
            abstime=obj.abstime,
            uin=obj.uin,
            nickname=obj.nickname,
            **kwds,
        )

    @from_feed.register
    @classmethod
    def _(cls, obj: FeedData, **kwds):
        return cls(
            appid=obj.common.appid,
            typeid=obj.common.typeid,
            fid=obj.fid,
            abstime=obj.abstime,
            uin=obj.userinfo.uin,
            nickname=obj.userinfo.nickname,
            unikey=obj.common.orgkey,
            curkey=obj.common.curkey,
            islike=obj.like.isliked,
            **kwds,
        )

    def set_frominfo(self, info: HtmlInfo):
        self.curkey = info.curkey
        self.unikey = info.unikey
        self.islike = bool(info.islike)
        self.topicId = info.topicid
        self.nickname = self.nickname or info.nickname


@dataclass
class BaseDetail:
    entities: List[ConEntity] = field(default_factory=list)
    forward: Union["FeedContent", str, None] = None
    """unikey to the feed, or the content itself."""
    media: List[VisualMedia] = field(default_factory=list)

    @singledispatchmethod
    def set_detail(self, obj) -> None:
        raise TypeError("Invalid type", type(obj))

    @set_detail.register
    def _set_detail_from_detail(self, obj: FeedDetailRep):
        self.entities = obj.entities or []
        if isinstance(self, BaseFeed):
            self.nickname = self.nickname or obj.name

        if obj.rt_uin:
            assert obj.rt_con
            unikey = LikeData.persudo_unikey(311, obj.rt_uin, fid=obj.rt_fid)
            self.forward = FeedContent(
                appid=311,
                typeid=2,
                fid=obj.rt_fid,
                uin=obj.rt_uin,
                nickname=obj.rt_uinname,
                abstime=approx_ts(obj.rt_createTime) if obj.rt_createTime else 0,
                curkey=unikey,
                unikey=unikey,
                entities=obj.rt_con.entities or [],
            )
        if obj.pic:
            assert all(i.valid_url() for i in obj.pic)
            if self.forward is None:
                self.media = [VisualMedia.from_pic(i) for i in obj.pic]
            else:
                assert isinstance(self.forward, FeedContent)
                self.forward.media = [VisualMedia.from_pic(i) for i in obj.pic]

        if obj.video:
            if self.forward is None:
                self.media = self.media or []
                self.media.extend(VisualMedia.from_video(i) for i in obj.video)
            else:
                assert isinstance(self.forward, FeedContent)
                self.forward.media = self.forward.media or []
                self.forward.media.extend(VisualMedia.from_video(i) for i in obj.video)

    @set_detail.register
    def _set_detail_from_feeddata(self, obj: FeedData):
        self.entities = split_entities(obj.summary.summary)
        if obj.original:
            if isinstance(obj.original, FeedOriginal):
                org = obj.original
                self.forward = FeedContent(
                    entities=split_entities(org.summary.summary),
                    appid=org.common.appid,
                    typeid=org.common.typeid,
                    fid=org.fid,
                    abstime=org.common.time,
                    uin=org.userinfo.uin,
                    nickname=org.userinfo.nickname,
                    curkey=org.common.curkey,
                    unikey=org.common.orgkey,
                )
                if org.pic:
                    self.forward.media = [VisualMedia.from_pic(i) for i in org.pic.picdata]
                if org.video:
                    self.forward.media.insert(0, VisualMedia.from_video(org.video))

            elif isinstance(obj.original, Share):
                self.forward = obj.original.common.orgkey

        if obj.pic:
            self.media = [VisualMedia.from_pic(i) for i in obj.pic.picdata]
        if obj.video:
            self.media.insert(0, VisualMedia.from_video(obj.video))

    @set_detail.register
    def set_fromhtml(self, obj: HtmlContent):
        if obj.entities:
            self.entities = obj.entities
        if obj.pic:
            self.media = [VisualMedia.from_pic(i) for i in obj.pic]


@dataclass
class FeedContent(BaseDetail, BaseFeed):
    """FeedContent is feed with contents. This might be the common structure to
    represent a feed as what it's known."""

    def __hash__(self) -> int:
        media_hash = hash(tuple(i.raw for i in self.media)) if self.media else 0
        return hash((self.uin, self.abstime, self.forward, media_hash))
