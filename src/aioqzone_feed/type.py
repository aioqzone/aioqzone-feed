from dataclasses import dataclass, field
from typing import List, Optional, Union

from aioqzone.model import FeedData, ProfileFeedData
from aioqzone.model.api.feed import FeedOriginal, FeedVideo, PicData, Share
from aioqzone.model.api.profile import ProfilePicData
from aioqzone.model.protocol import ConEntity
from aioqzone.utils.entity import split_entities

FEED_TYPES = Union[FeedData, ProfileFeedData]


@dataclass
class VisualMedia:
    height: int
    width: int
    raw: str
    is_video: bool
    thumbnail: Optional[str] = None

    @classmethod
    def from_pic(cls, pic: Union[PicData, ProfilePicData]):
        if isinstance(pic, ProfilePicData):
            return cls.from_profile_picdata(pic)

        if pic.videodata.videourl:
            return cls.from_video(pic.videodata)

        raw = pic.photourl.largest
        thumb = pic.photourl.smallest
        return cls(
            is_video=False,
            height=pic.origin_height,
            width=pic.origin_width,
            raw=str(raw.url),
            thumbnail=str(thumb.url),
        )

    @classmethod
    def from_video(cls, video: FeedVideo):
        assert video.videourl
        cover = video.coverurl.largest
        return cls(
            height=cover.height,
            width=cover.width,
            thumbnail=str(cover.url),
            raw=str(video.videourl),
            is_video=True,
        )

    @classmethod
    def from_profile_picdata(cls, pic: ProfilePicData):
        raw = pic.photourl.largest
        thumb = pic.photourl.smallest
        return cls(
            is_video=False,
            height=raw.height,
            width=raw.width,
            raw=str(raw.url),
            thumbnail=str(thumb.url),
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
        short string and is commonly used by multiple shares. So do not distinguish all feeds on this field.
    """
    abstime: int
    """Feed created time. common alias: `created_time`"""
    uin: int
    """Feed owner :external+aioqzone:term:`uin`."""
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

    @classmethod
    def from_feed(cls, obj: Union[FeedData, ProfileFeedData], **kwds):
        return cls(
            appid=obj.common.appid,
            typeid=obj.common.typeid,
            fid=obj.fid,
            abstime=obj.abstime,
            uin=obj.userinfo.uin,
            nickname=obj.userinfo.nickname,
            unikey=str(obj.common.orgkey),
            curkey=str(obj.common.curkey),
            islike=obj.like.isliked,
            **kwds,
        )


@dataclass
class BaseDetail:
    entities: List[ConEntity] = field(default_factory=list)
    forward: Union["FeedContent", str, None] = None
    """unikey to the feed, or the content itself."""
    media: List[VisualMedia] = field(default_factory=list)

    def set_detail(self, obj: Union[FeedData, ProfileFeedData]):
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
                    curkey=str(org.common.curkey),
                    unikey=str(org.common.orgkey),
                )
                if org.pic:
                    self.forward.media = [VisualMedia.from_pic(i) for i in org.pic.picdata]
                if org.video:
                    self.forward.media.insert(0, VisualMedia.from_video(org.video))

            elif isinstance(obj.original, Share):
                self.forward = str(obj.original.common.orgkey)

        if obj.pic:
            self.media = [VisualMedia.from_pic(i) for i in obj.pic.picdata]
        if isinstance(obj, FeedData) and obj.video:
            self.media.insert(0, VisualMedia.from_video(obj.video))


@dataclass
class FeedContent(BaseDetail, BaseFeed):
    """FeedContent is feed with contents. This might be the common structure to
    represent a feed as what it's known."""

    def __hash__(self) -> int:
        media_hash = hash(tuple(i.raw for i in self.media)) if self.media else 0
        return hash((self.uin, self.abstime, self.forward, media_hash))
