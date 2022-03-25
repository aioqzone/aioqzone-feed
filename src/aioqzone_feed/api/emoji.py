"""Translate emoji representation to text."""
import asyncio
import re
from typing import Any, Callable, Coroutine, Dict, List, Type, Union

import qzemoji as qe
from aioqzone.type import AtEntity, ConEntity, TextEntity
from lxml.html import HtmlElement, fromstring
from qzemoji.utils import build_tag

from ..type import FeedContent

TAG_RE = re.compile(r"\[em\]e(\d+)\[/em\]")
URL_RE = re.compile(r"https?://[\w\.]+/qzone/em/e(\d+)\.\w{3}")

t2a: Dict[Type[ConEntity], list[str]] = {
    TextEntity: ["con"],
    AtEntity: ["nick"],
}


async def query_wrap(eid: int) -> str:
    s = await qe.query(eid)
    if s is None:
        return build_tag(eid)
    if not re.fullmatch(r"[^\u0000-\uFFFF]*", s):
        return f"[/{s}]"
    return s


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
        assert not pending
        excs = list(filter(None, (i.exception() for i in done)))
        if excs:
            raise RuntimeError(*excs)
    return "".join(r)


async def trans_tag(text: str):
    return await sub(TAG_RE, lambda m: query_wrap(int(m.group(1))), text)


async def trans_detail(feed: FeedContent) -> FeedContent:
    tasks = []

    def repl_attr(obj: object, attr: str):
        t = asyncio.create_task(trans_tag(getattr(obj, attr)))
        t.add_done_callback(lambda t: setattr(obj, attr, t.result()))
        tasks.append(t)

    repl_attr(feed, "nickname")
    if feed.entities:
        for e in feed.entities:
            al = t2a.get(type(e), None)
            if al is None:
                continue
            for a in al:
                repl_attr(e, a)

    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
        excs = list(filter(None, (i.exception() for i in done)))
        if excs:
            raise RuntimeError(*excs)
    return feed


async def trans_html(txtbox: Union[HtmlElement, str]) -> HtmlElement:
    if isinstance(txtbox, str):
        txtbox = fromstring(txtbox)
    assert isinstance(txtbox, HtmlElement)
    imgs: List[HtmlElement] = txtbox.cssselect("img")

    tasks = []
    for i in imgs:
        m = URL_RE.match(i.get("src", ""))
        if not m:
            continue
        t = asyncio.create_task(query_wrap(int(m.group(1))))
        t.add_done_callback(
            lambda t, e=i: setattr(e, "tail", t.result() + (e.tail or "")) or e.drop_tree()
        )
        tasks.append(t)

    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
        excs = list(filter(None, (i.exception() for i in done)))
        if excs:
            raise RuntimeError(*excs)
    return txtbox
