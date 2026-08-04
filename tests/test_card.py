"""The contract card - the one surface that only renders from 2027."""
from __future__ import annotations
import importlib.util, sys, types, pathlib

import pytest
from halfmen import engine


def _card():
    """Import app.py's contract_card without booting Streamlit's page."""
    import streamlit as st
    src = pathlib.Path("app.py").read_text()
    ns = {}
    start = src.index("def contract_card(")
    end = src.index("def ledger_table(")
    from halfmen import config, theme
    exec("from halfmen import config, engine, theme\n"
         "from html import escape as _e\n"
         "def esc(x): return _e(str(x))\n" + src[start:end], ns)
    return ns["contract_card"]


CARD = _card()


def test_a_player_at_the_wall_gets_the_red_rail():
    p = engine.price_regular("1", "Quinshon Judkins", "RB", draft_round=9, year=4, adp_round=1)
    html = CARD(p)
    assert 'class="contract wall' in html
    assert "wall" in html and "no price" in html


def test_a_franchise_tag_gets_the_gold_rail_and_chip():
    p = engine.price_franchise("1", "x", "RB", peak_round=5, year=4, adp_round=1)
    html = CARD(p)
    assert 'class="contract fr' in html and 'chip solid">Franchise' in html


def test_a_rookie_keeper_gets_the_violet_chip():
    p = engine.price_rookie("1", "Jeremiah Smith", "WR", slot=0, last_round=14, adp_round=1)
    html = CARD(p)
    assert 'chip mag">Rookie keeper' in html
    assert "no clock" in html, "rookie keepers show no wall"


def test_real_surplus_earns_the_lime_rail():
    p = engine.price_regular("1", "x", "WR", draft_round=12, year=1, adp_round=4)
    assert 'class="contract pick' in CARD(p)


def test_a_bump_is_called_out():
    from collections import Counter
    owned = Counter({r: 1 for r in range(1, 15)})
    del owned[7]
    p = engine.price_regular("1", "Ollie Gordon II", "RB", draft_round=7, year=1, adp_round=5)
    engine.allocate([p], owned)
    assert "Bumped from R7" in CARD(p) and "R6" in CARD(p)


def test_the_rookie_draft_premium_is_labelled():
    p = engine.price_regular("1", "x", "WR", draft_round=None, year=1, adp_round=1,
                             from_rookie_draft=True)
    assert "Rookie-draft R5" in CARD(p)


def test_names_are_escaped():
    p = engine.price_regular("1", "<script>x</script>", "WR", draft_round=9, year=1, adp_round=4)
    assert "<script>" not in CARD(p)
