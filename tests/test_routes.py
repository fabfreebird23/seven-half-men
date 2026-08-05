"""Every route in the bottom bar has to render something.

There are sixteen leaves behind two popovers now, and most of them are dark in
year one - an empty roster, no transactions, no keepers. A route that raises or
renders nothing would be invisible until the season started, so this walks all
of them with Streamlit's own harness.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SRC = Path(APP).read_text()


def _groups():
    ns = {}
    exec(re.search(r"GROUPS = \{.*?\n\}\n", SRC, re.S).group(0), ns)
    return ns["GROUPS"]


def routes():
    yield {"p": "home"}
    yield {"p": "rules"}
    for section, groups in _groups().items():
        for gk, _glabel, leaves in groups:
            for lk, _llabel in leaves:
                yield {"p": section, "g": gk, "t": lk}


ALL = list(routes())


def test_there_are_sixteen_leaves_plus_two_flat_pages():
    assert len(ALL) == 18


@pytest.mark.parametrize("qp", ALL, ids=lambda q: "/".join(q.values()))
def test_route_renders_without_raising(qp):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(qp)
    at.run()
    assert not at.exception, "%s raised: %s" % (qp, [e.value for e in at.exception])


@pytest.mark.parametrize("qp", ALL, ids=lambda q: "/".join(q.values()))
def test_route_renders_actual_content(qp):
    """Not just 'no crash' - a leaf that silently renders nothing is the failure
    mode this refactor could plausibly introduce."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(qp)
    at.run()
    body = "".join(m.value for m in at.markdown)
    assert len(body) > 400, "%s rendered %d chars" % (qp, len(body))
