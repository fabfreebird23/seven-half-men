"""Whose pick is it, and how long have they got.

A 24-hour clock makes the draft a fortnight-long background event, so the two
things that have to be right are the snake maths and the deadline. Getting the
snake wrong would put the wrong name on the clock for a whole day.
"""
from __future__ import annotations

import pytest

from halfmen import config, live

ORDER = ["a", "b", "c", "d"]


def fake(status="drafting", rounds=2, made=0, timer=86400, snake=True,
         last=1_000_000_000_000):
    return {
        "draft_id": "d1", "status": status, "type": "snake" if snake else "linear",
        "settings": {"teams": 4, "rounds": rounds, "pick_timer": timer, "player_type": 1},
        "draft_order": {o: i + 1 for i, o in enumerate(ORDER)},
        "last_picked": last, "start_time": last,
    }, [{"round": 1, "draft_slot": i + 1, "pick_no": i + 1, "metadata": {}}
        for i in range(made)]


def wire(monkeypatch, draft, picks):
    monkeypatch.setattr(live.sleeper, "get_drafts", lambda lid: [draft])
    monkeypatch.setattr(live.sleeper, "get_draft_picks", lambda did, ttl=900: picks)


@pytest.mark.parametrize("made,expect_owner,expect_pick", [
    (0, "a", 1), (1, "b", 2), (3, "d", 4),      # round one runs forwards
    (4, "d", 1), (5, "c", 2), (7, "a", 4),      # round two snakes back
])
def test_the_snake_puts_the_right_name_on_the_clock(monkeypatch, made, expect_owner, expect_pick):
    d, p = fake(made=made)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["on_clock"] == expect_owner
    assert s["pick"] == expect_pick
    assert s["round"] == (1 if made < 4 else 2)


def test_a_linear_board_does_not_snake(monkeypatch):
    d, p = fake(made=4, snake=False)
    wire(monkeypatch, d, p)
    assert live.state(live.ROOKIE, "lg")["on_clock"] == "a"


def test_nobody_is_on_the_clock_before_it_starts_or_after_it_ends(monkeypatch):
    d, p = fake(status="pre_draft")
    wire(monkeypatch, d, p)
    assert live.state(live.ROOKIE, "lg")["on_clock"] is None

    d, p = fake(made=8)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["on_clock"] is None and s["made"] == s["total"]


def test_the_deadline_is_the_last_pick_plus_the_timer(monkeypatch):
    d, p = fake(last=1_000_000_000_000)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["deadline"] == 1_000_000_000 + 86400


def test_countdown_reads_the_way_a_person_would_say_it():
    assert live.countdown(1000 + 3600 * 6 + 60 * 12, now=1000) == "6h 12m left"
    assert live.countdown(1000 + 90 * 60, now=1000) == "1h 30m left"
    assert live.countdown(1000 + 60 * 45, now=1000) == "45m left"
    assert live.countdown(1000 + 86400 * 2, now=1000) == "2d 0h left"
    assert "past the deadline" in live.countdown(500, now=1000)


def test_a_round_count_that_disagrees_with_the_rulebook_is_named(monkeypatch):
    """The live one: the rookie draft went up as 16 ROUNDS, not 16 picks. At a
    day a pick that is 128 days instead of 16, and a board that quietly rendered
    the league's intention would have hidden it."""
    d, p = fake(rounds=16)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    warn = live.disagreements(s, live.ROOKIE)
    assert warn and "16 rounds" in warn[0] and "64 picks" in warn[0]


def test_agreement_is_silent(monkeypatch):
    d, p = fake(rounds=config.rookie_rounds())
    wire(monkeypatch, d, p)
    monkeypatch.setattr(live, "_drawn_order", lambda kind: [])
    assert live.disagreements(live.state(live.ROOKIE, "lg"), live.ROOKIE) == []


def test_a_board_order_unlike_the_drum_is_not_a_problem(monkeypatch):
    """The drum sets a SELECTION order - who picks a slot first - and first
    choice takes any spot they want. So Sleeper's board is expected to differ,
    and flagging it would cry wolf on the rules working as designed."""
    d, p = fake(rounds=config.rookie_rounds())
    wire(monkeypatch, d, p)
    monkeypatch.setattr(live, "_drawn_order", lambda kind: ["d", "c", "b", "a"])
    assert live.disagreements(live.state(live.ROOKIE, "lg"), live.ROOKIE) == []


def test_the_slots_show_what_each_manager_did_with_their_choice(monkeypatch):
    """The only record anywhere of who took which spot off the board."""
    d, p = fake(rounds=config.rookie_rounds())
    wire(monkeypatch, d, p)
    monkeypatch.setattr(live, "_drawn_order", lambda kind: ["d", "c", "b", "a"])
    got = live.slots_chosen(live.state(live.ROOKIE, "lg"), live.ROOKIE)
    assert got[0] == (1, "a", 4), "a drew last in the drum and took the 1 slot"
    assert got[3] == (4, "d", 1), "d had first choice and took the 4 slot"


# --------------------------------------------------------------------------
# Sleeper would not accept a 2-round rookie draft, so it runs long and gets
# stopped by hand. Everything past pick 16 is not a pick in this league.
# --------------------------------------------------------------------------

def over(made):
    """A 16-round Sleeper draft against a 2-round rulebook, at 4 teams."""
    d, _ = fake(rounds=16)
    picks = [{"round": i // 4 + 1, "draft_slot": i % 4 + 1, "pick_no": i + 1,
              "player_id": str(i), "metadata": {"first_name": "P%d" % i, "last_name": "X"}}
             for i in range(made)]
    return d, picks


def test_progress_counts_against_the_rulebook_not_sleeper(monkeypatch):
    d, p = over(3)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["total"] == 64, "what Sleeper is running"
    assert s["league_total"] == config.rookie_rounds() * 4, "what the league is running"
    assert s["over_run"]


def test_the_pick_before_the_end_is_flagged(monkeypatch):
    league_total = config.rookie_rounds() * 4
    d, p = over(league_total - 1)
    wire(monkeypatch, d, p)
    assert live.state(live.ROOKIE, "lg")["last_before_stop"]


def test_stop_now_fires_the_moment_the_last_pick_lands(monkeypatch):
    league_total = config.rookie_rounds() * 4
    d, p = over(league_total)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["stop_now"] and s["voided"] == 0


def test_picks_past_the_stop_point_are_counted_as_overrun(monkeypatch):
    league_total = config.rookie_rounds() * 4
    d, p = over(league_total + 3)
    wire(monkeypatch, d, p)
    s = live.state(live.ROOKIE, "lg")
    assert s["voided"] == 3
    assert len(live.rows(s)) == league_total, "the overrun picks are not shown as real"
    assert len(live.rows(s, counted_only=False)) == league_total + 3


def test_history_classifies_a_rookie_draft_by_player_type_not_round_count():
    """The bug the misconfiguration would have caused: 16 rounds made the rookie
    draft look like a veteran draft, which would have priced every rookie against
    a veteran round with no R5 premium and no rookie-keeper status."""
    from halfmen import history
    d = {"settings": {"rounds": 16, "player_type": 1}}
    assert history._draft_kind(d, first_season=True) == "rookie"


def test_history_drops_picks_past_the_rulebook_rounds(monkeypatch):
    from halfmen import history
    d = {"draft_id": "d1", "settings": {"rounds": 16, "player_type": 1}}
    monkeypatch.setattr(history.sleeper, "get_draft_picks",
                        lambda did, **k: [{"round": r} for r in range(1, 17)])
    kept = history._picks_for(d, "rookie")
    assert len(kept) == config.rookie_rounds()
    assert max(p["round"] for p in kept) == config.rookie_rounds()
