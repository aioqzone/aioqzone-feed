import pytest
import qzemoji as qe

pytestmark = pytest.mark.asyncio

qe.enable_auto_update = False


async def test_tag():
    from aioqzone_feed.api.emoji import trans_tag

    assert "[/微笑][/撇嘴][/色]" == await trans_tag("[em]e100[/em][em]e101[/em][em]e102[/em]")
    assert "阿巴阿巴🐷啊对对🐷对" == await trans_tag("阿巴阿巴[em]e400343[/em]啊对对[em]e400343[/em]对")
    assert "[em]e1111111[/em]" == await trans_tag("[em]e1111111[/em]")


async def test_html():
    html1 = "<div class='txtbox'><img src='http://qzonestyle.gtimg.cn/qzone/em/e100.png'></img><img src='http://qzonestyle.gtimg.cn/qzone/em/e101.png'></img><img src='http://qzonestyle.gtimg.cn/qzone/em/e102.png'></img></div>"
    html2 = "<div class='txtbox'><span>阿巴阿巴</span><img src='http://qzonestyle.gtimg.cn/qzone/em/e400343.png'></img><span>啊对对</span><img src='http://qzonestyle.gtimg.cn/qzone/em/e400343.png'></img>对</div>"
    from lxml.html import fromstring

    from aioqzone_feed.api.emoji import trans_html

    assert "[/微笑][/撇嘴][/色]" == (await trans_html(fromstring(html1))).text_content()
    assert "阿巴阿巴🐷啊对对🐷对" == (await trans_html(fromstring(html2))).text_content()
