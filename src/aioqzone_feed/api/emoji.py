"""Translate emoji representation to text."""
import asyncio
import re
from typing import Any, Callable, Coroutine

from lxml.html import fromstring
from lxml.html import HtmlElement
import qzemoji as qe
from qzemoji.utils import build_tag

from ..type import FeedContent

TAG_RE = re.compile(r"\[em\]e(\d+)\[/em\]")
URL_RE = re.compile(r"https?://[\w\.]+/qzone/em/e(\d+)\.\w{3}")


async def sub(
    pattern: re.Pattern, repl: Callable[[re.Match], Coroutine[Any, Any, str]], text: str
):
    """
    The sub function is a async-version of :meth:`re.sub`.
    It works like pattern.sub(repl, text), except for this `repl` is an async-function.

    :param pattern: regex expression.
    :param repl: Used to replace the matched text. Input an :class:`re.Match`, returns a string, async.
    :param text: String to be searched.
    :return: replaced string.
    """
    r, tasks = [], []
    base = 0
    for i, m in enumerate(pattern.finditer(text)):
        fr, to = m.span(0)
        r.append(text[base:fr])  # save un-replaced string as is
        task = asyncio.create_task(repl(m))
        task.add_done_callback(lambda t, idx=i: r.__setitem__(idx, r[idx] + t.result()))
        tasks.append(task)
        base = to
    r.append(text[base:])
    if tasks:
        done, pending = await asyncio.wait(tasks)
        excs = list(filter(None, (i.exception() for i in done)))
        if excs:
            raise RuntimeError(*excs)
    return "".join(r)


async def trans_tag(text: str):
    return await sub(TAG_RE, lambda m: qe.query(int(m.group(1)), default=build_tag), text)


async def trans_detail(feed: FeedContent) -> FeedContent:
    tasks = [
        (t := asyncio.create_task(trans_tag(getattr(feed, i))))
        and t.add_done_callback(lambda t: setattr(feed, i, t.result()))
        or t
        for i in ["nickname", "content"]
    ]
    done, pending = await asyncio.wait(tasks)
    assert not pending
    return feed


async def trans_html(txtbox: HtmlElement | str) -> HtmlElement:
    if isinstance(txtbox, str):
        txtbox = fromstring(txtbox)
    assert isinstance(txtbox, HtmlElement)
    imgs: list[HtmlElement] = txtbox.cssselect("img")
    tasks = [
        (t := asyncio.create_task(qe.query(int(m.group(1)), default=build_tag)))
        and t.add_done_callback(
            lambda t, e=i: setattr(e, "tail", t.result() + (e.tail or "")) or e.drop_tree()
        )
        or t
        for i in imgs
        if (m := URL_RE.match(i.get("src", "")))
    ]
    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
    return txtbox
