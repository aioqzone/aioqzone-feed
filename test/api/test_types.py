from aioqzone.utils.html import HtmlContent

from aioqzone_feed.type import BaseDetail


def test_set_detail():
    detail = BaseDetail()
    detail.set_detail(HtmlContent(entities=[], pic=[], album=None))
