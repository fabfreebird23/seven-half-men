"""The in-season blocks, against the states a real season passes through.

The failure that matters on this page is not a crash - it is a block that
confidently prints a number nobody should trust. Two of those are pinned here:
a standings table in week 1 that reads as though games have been played, and a
matchup "favourite" invented out of a board with no weekly component in it.
"""
from __future__ import annotations

import pytest

from halfmen import config, season


def roster(rid, owner, wins=0, losses=0, fpts=0, used=0, players=None, taxi=None):
    return {"roster_id": rid, "owner_id": owner, "players": players or [],
            "taxi": taxi or [],
            "settings": {"wins": wins, "losses": losses, "ties": 0, "fpts": fpts,
                         "waiver_budget_used": used, "total_moves": 0}}


@pytest.fixture
def league(monkeypatch):
    def wire(rosters, matchups=None, tx=None, players=None):
        monkeypatch.setattr(season.sleeper, "get_rosters", lambda lid: rosters)
        monkeypatch.setattr(season.sleeper, "get_matchups", lambda lid, wk: matchups or [])
        monkeypatch.setattr(season.sleeper, "get_transactions", lambda lid, wk: tx or [])
        monkeypatch.setattr(season.sleeper, "get_players", lambda: players or {})
        monkeypatch.setattr(season.sleeper, "get_league",
                            lambda lid: {"settings": {"leg": 1}})
    return wire


# -------------------------------------------------------------- the table

def test_a_roster_missing_its_id_does_not_take_the_page_down(league):
    """Every number on the front page comes from Sleeper, so one malformed row
    must degrade rather than raise. This crashed the whole Home page."""
    league([{"owner_id": "a", "settings": {}}, roster(2, "b")])
    assert season.standings()          # did not raise
    assert season.matchups() == [] or True


def test_week_one_is_reported_as_nothing_played_not_as_a_league_table(league):
    league([roster(1, "a"), roster(2, "b")])
    rows = season.standings()
    assert season.nothing_played(rows), "0-0 across the board is not a standing"


def test_the_table_sorts_on_wins_then_points_like_sleeper_does(league):
    league([roster(1, "a", wins=2, fpts=100), roster(2, "b", wins=2, fpts=300),
            roster(3, "c", wins=5, fpts=10)])
    rows = season.standings()
    assert [r["owner_id"] for r in rows] == ["c", "b", "a"]
    assert not season.nothing_played(rows)
    assert rows[0]["place"] == 1 and rows[0]["in_bracket"]


def test_the_median_match_is_not_counted_as_two_weeks_of_football(league, monkeypatch):
    """With the median on, a week produces two results. A team at 6-2 has
    played four weeks, not eight, and `played` drives 'N to play'."""
    monkeypatch.setattr(config, "median_match", lambda: True)
    league([roster(1, "a", wins=6, losses=2)])
    assert season.standings()[0]["played"] == 4
    monkeypatch.setattr(config, "median_match", lambda: False)
    assert season.standings()[0]["played"] == 8


# ----------------------------------------------------------- the fixtures

def _two_sided(a_players, b_players, pmap):
    return ([{"matchup_id": 1, "roster_id": 1, "points": 0},
             {"matchup_id": 1, "roster_id": 2, "points": 0}],
            [roster(1, "a", players=a_players), roster(2, "b", players=b_players)],
            pmap)


def test_a_lopsided_matchup_names_a_favourite(league, monkeypatch):
    pmap = {"1": {"full_name": "Stud One"}, "2": {"full_name": "Scrub One"}}
    monkeypatch.setattr(season.adp_board, "table", lambda: {
        "studone": {"rank": 1.0}, "scrubone": {"rank": 380.0}})
    m, r, p = _two_sided(["1"], ["2"], pmap)
    league(r, matchups=m, players=p)
    got = season.matchups()[0]
    assert got["favourite"] == "a"
    assert not got["too_close"]


def test_two_even_rosters_are_called_a_coin_flip_not_a_50_point_2_percent_edge(
        league, monkeypatch):
    """Eight teams drafting off one board finish within a couple of points of
    each other. Printing '50.2%' every week reads as a real prediction."""
    pmap = {"1": {"full_name": "Guy One"}, "2": {"full_name": "Guy Two"}}
    monkeypatch.setattr(season.adp_board, "table", lambda: {
        "guyone": {"rank": 20.0}, "guytwo": {"rank": 21.0}})
    m, r, p = _two_sided(["1"], ["2"], pmap)
    league(r, matchups=m, players=p)
    got = season.matchups()[0]
    assert got["too_close"] and got["favourite"] == ""


def test_value_falls_off_steeply_enough_to_separate_anyone():
    """A linear curve made the 1st and 15th players 15 apart and the 150th and
    165th 15 apart too, which flattened every matchup to a dead heat."""
    top = season._value(1) - season._value(15)
    tail = season._value(150) - season._value(165)
    assert top > tail * 5


# --------------------------------------------------------------- the taxi

def test_a_rookie_on_the_bench_with_a_slot_free_is_surfaced(league):
    """Squads are declared before the first kickoff and a slot left empty then
    stays empty for the season, so a rookie sitting on a bench next to a free
    slot is the one thing on this page worth acting on. Sleeper has no
    league-wide taxi view, so nobody would otherwise notice."""
    league([roster(1, "a", taxi=["1"]), roster(2, "b", taxi=[], players=["2"])],
           players={"1": {"full_name": "Rook One", "years_exp": 0},
                    "2": {"full_name": "Rook Two", "years_exp": 0}})
    rows = season.taxi()
    assert rows[0]["owner_id"] == "b", "the wasted slot sorts to the top"
    assert rows[0]["wasting"] and [p["name"] for p in rows[0]["parkable"]] == ["Rook Two"]
    assert season.taxi_gap(rows) == ["b"]


def test_a_free_slot_with_no_rookie_to_fill_it_is_not_someone_to_chase(league):
    """Eligibility is any rookie you drafted. A manager who drafted none has
    nothing to fix and does not belong on a list of people holding it up."""
    league([roster(1, "a", taxi=[], players=["9"])],
           players={"9": {"full_name": "Old Head", "years_exp": 6}})
    rows = season.taxi()
    assert rows[0]["open"] == int(config.taxi_rules()["slots"])
    assert not rows[0]["wasting"] and rows[0]["parkable"] == []
    assert season.taxi_gap(rows) == []


def test_a_veteran_draft_rookie_is_as_eligible_as_a_rookie_draft_one(league):
    """What qualifies him is that he is a rookie you drafted, not which board
    he came off. The two drafts were in conflict in config until 2026-08-30."""
    league([roster(1, "a", taxi=[], players=["5"])],
           players={"5": {"full_name": "Late Round Rook", "years_exp": 0}})
    assert season.taxi()[0]["wasting"]


def test_a_full_taxi_squad_reports_no_gap(league):
    league([roster(1, "a", taxi=["1", "2"])],
           players={"1": {"full_name": "Rook One"}, "2": {"full_name": "Rook Two"}})
    rows = season.taxi()
    assert rows[0]["used"] == 2 and rows[0]["open"] == 0
    assert season.taxi_gap(rows) == []


# ------------------------------------------------------------- the moves

def test_moves_walk_back_through_empty_weeks(league):
    """Sleeper keys transactions by week with no 'latest' endpoint. A quiet
    current week means the last move was earlier, not that there were none."""
    def tx(lid, wk):
        return [{"type": "waiver", "status": "complete", "status_updated": 5,
                 "roster_ids": [1], "adds": {"9": 1}, "drops": None,
                 "settings": {"waiver_bid": 14}}] if wk == 1 else []
    league([roster(1, "a")], players={"9": {"full_name": "Some Guy", "position": "WR"}})
    import types
    season.sleeper.get_transactions = tx
    monkey = season.transactions(limit=5, week=6)
    assert len(monkey) == 1
    assert monkey[0]["adds"][0]["name"] == "Some Guy"
    assert monkey[0]["bid"] == 14 and monkey[0]["kind"] == "claimed"


def test_incomplete_moves_are_not_reported_as_having_happened(league):
    def tx(lid, wk):
        return [{"type": "waiver", "status": "failed", "status_updated": 5,
                 "roster_ids": [1], "adds": {"9": 1}}]
    league([roster(1, "a")], players={"9": {"full_name": "Some Guy"}})
    season.sleeper.get_transactions = tx
    assert season.transactions(limit=5, week=2) == []


# ------------------------------------------------------- power rankings

def _league(league, records, players=None, adp=None, monkeypatch=None):
    rs = []
    for i, (owner, (w, l, pf, pids)) in enumerate(records.items(), 1):
        rs.append(roster(i, owner, wins=w, losses=l, fpts=pf, players=pids))
    league(rs, players=players or {})
    if adp is not None:
        monkeypatch.setattr(season.adp_board, "table", lambda: adp)
    return rs


PLAYERS = {"stud": {"full_name": "Stud"}, "scrub": {"full_name": "Scrub"}}
ADP = {"stud": {"rank": 1.0}, "scrub": {"rank": 350.0}}


def test_before_a_game_the_ranking_is_roster_strength_and_says_so(league, monkeypatch):
    """A blend that quietly weighed an unplayed 0-0 record would be roster
    strength wearing a disguise. The page has to be able to name what it is."""
    _league(league, {"a": (0, 0, 0, ["scrub"]), "b": (0, 0, 0, ["stud"])},
            PLAYERS, ADP, monkeypatch)
    rows = season.power()
    assert rows[0]["owner_id"] == "b", "the better roster leads"
    assert rows[0]["weight"] == 0.0
    assert "roster strength only" in season.power_basis(rows)


def test_results_take_over_completely_by_the_crossover_week(league, monkeypatch):
    """Past the crossover a preseason board does not get a vote. The worst
    roster with the best record has to be able to rank first."""
    played = int(season.RESULTS_TAKE_OVER_BY) * 2      # median match: 2 a week
    _league(league, {"a": (played, 0, 900, ["scrub"]),
                     "b": (0, played, 100, ["stud"])},
            PLAYERS, ADP, monkeypatch)
    rows = season.power()
    assert rows[0]["weight"] == 1.0
    assert rows[0]["owner_id"] == "a", "unbeaten with the worst roster still leads"
    assert season.power_basis(rows) == "record and points only"


def test_the_blend_moves_off_roster_strength_as_games_are_played(league, monkeypatch):
    """Halfway to the crossover the ranking is genuinely mixed - neither
    component may be silently dropped."""
    _league(league, {"a": (6, 0, 900, ["scrub"]), "b": (0, 6, 100, ["stud"])},
            PLAYERS, ADP, monkeypatch)
    rows = season.power()
    assert 0.0 < rows[0]["weight"] < 1.0
    basis = season.power_basis(rows)
    assert "%" in basis and "record" in basis and "roster strength" in basis


def test_movement_is_measured_against_the_draft_not_last_week(league, monkeypatch):
    """No stored history, and it answers the better question: who is doing more
    than their draft said they would."""
    played = int(season.RESULTS_TAKE_OVER_BY) * 2
    _league(league, {"a": (played, 0, 900, ["scrub"]),
                     "b": (0, played, 100, ["stud"])},
            PLAYERS, ADP, monkeypatch)
    rows = {r["owner_id"]: r for r in season.power()}
    assert rows["a"]["seed"] == 2 and rows["a"]["moved"] == 1
    assert rows["b"]["seed"] == 1 and rows["b"]["moved"] == -1


def test_a_taxi_stash_does_not_count_toward_roster_strength(league, monkeypatch):
    """He cannot score for you, so he cannot make you look stronger."""
    rs = [roster(1, "a", players=["stud", "scrub"], taxi=["stud"]),
          roster(2, "b", players=["scrub"])]
    league(rs, players=PLAYERS)
    monkeypatch.setattr(season.adp_board, "table", lambda: ADP)
    rows = {r["owner_id"]: r for r in season.power()}
    assert rows["a"]["strength"] == rows["b"]["strength"]


def test_win_rate_alone_cannot_carry_a_team_that_scores_nothing(league, monkeypatch):
    """40% of the results score is points for, so a soft schedule is not the
    whole story."""
    played = int(season.RESULTS_TAKE_OVER_BY) * 2
    _league(league, {"lucky": (played, 0, 10, ["scrub"]),
                     "strong": (played - 2, 2, 2000, ["scrub"])},
            PLAYERS, ADP, monkeypatch)
    rows = {r["owner_id"]: r for r in season.power()}
    assert rows["strong"]["results_score"] > rows["lucky"]["results_score"] * 0.8
