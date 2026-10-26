"""The two drums and their three guardrails."""
from __future__ import annotations

import random

import pytest

from halfmen import config, lottery

# A simulated 2029: Taco Bandit won the title from the 4 seed at 8-6, so the
# champion floor has something to bite on.
STANDINGS = [
    {"owner_id": "bijan",  "wins": 11, "final_rank": 2, "champion": False},
    {"owner_id": "beant",  "wins": 10, "final_rank": 3, "champion": False},
    {"owner_id": "amonra", "wins": 9,  "final_rank": 4, "champion": False},
    {"owner_id": "taco",   "wins": 8,  "final_rank": 1, "champion": True},
    {"owner_id": "clay",   "wins": 7,  "final_rank": 5, "champion": False},
    {"owner_id": "whig",   "wins": 6,  "final_rank": 7, "champion": False},
    {"owner_id": "later",  "wins": 4,  "final_rank": 8, "champion": False},
    {"owner_id": "nabers", "wins": 3,  "final_rank": 6, "champion": False},
]


def rookie_drum(locked=()):
    return lottery.build_drum(STANDINGS, "record", locked_out=locked)


def vet_drum(locked=()):
    return lottery.build_drum(STANDINGS, "final", locked_out=locked)


# ---------------------------------------------------------------- weighting

def test_rookie_drum_orders_by_record_worst_first():
    seats = rookie_drum()
    assert [s.owner_id for s in seats][:3] == ["nabers", "later", "whig"]


def test_veteran_drum_orders_by_final_standing():
    """A Chase-bracket win costs you veteran balls. Nabers had the worst record
    but won a Chase game, so he drops behind Later and Whig."""
    seats = vet_drum()
    assert [s.owner_id for s in seats][:3] == ["later", "whig", "nabers"]


def test_champion_is_forced_to_the_floor_whatever_the_record():
    for seats in (rookie_drum(), vet_drum()):
        assert seats[-1].owner_id == "taco"
        assert seats[-1].weight == min(s.weight for s in seats)


def test_weights_come_from_config_and_are_strictly_decreasing():
    seats = rookie_drum()
    ws = [s.weight for s in seats]
    assert ws == config.lottery_weights()
    assert all(a > b for a, b in zip(ws, ws[1:])), "the worst team must outrank the 6-8 team"


def test_the_worst_team_still_beats_the_third_worst():
    ws = config.lottery_weights()
    assert ws[0] > ws[2]


def test_compression_keeps_an_extra_loss_cheap():
    """The whole point of the compressed spread: going from 3rd-worst to worst
    is worth a lot less than it was under the steep weights."""
    comp, steep = config.lottery_weights(), config.lottery_weights(alt=True)
    assert (comp[0] - comp[2]) < (steep[0] - steep[2])


# ---------------------------------------------------------------- drawing

def test_selection_order_covers_every_team_exactly_once():
    order = lottery.draw(rookie_drum(), rng=random.Random(1))
    assert sorted(order) == sorted(s.owner_id for s in rookie_drum())


def test_locked_out_team_cannot_win_first_choice():
    seats = rookie_drum(locked=["nabers"])
    rng = random.Random(7)
    for _ in range(400):
        assert lottery.draw(seats, rng=rng)[0] != "nabers"


def test_locked_out_team_can_still_win_second_choice():
    """The lock-out covers first choice only, not the whole top two."""
    seats = rookie_drum(locked=["nabers"])
    rng = random.Random(9)
    seconds = {lottery.draw(seats, rng=rng)[1] for _ in range(600)}
    assert "nabers" in seconds


def test_the_lock_out_is_per_drum_not_league_wide():
    """Win first choice of the rookie draft and you are barred from the rookie
    drum next year — but the veteran drum does not care."""
    rookie = rookie_drum(locked=["nabers"])       # won the rookie drum last year
    vet = vet_drum(locked=[])                     # clean slate over here
    rng = random.Random(3)
    rookie_firsts, vet_firsts = set(), set()
    for _ in range(1500):
        res = lottery.draw_both(rookie, vet, rng=rng)
        rookie_firsts.add(res["rookie"][0])
        vet_firsts.add(res["veteran"][0])
    assert "nabers" not in rookie_firsts
    assert "nabers" in vet_firsts


def test_a_team_can_be_locked_out_of_both_drums_independently():
    rookie = rookie_drum(locked=["nabers"])
    vet = vet_drum(locked=["later"])
    rng = random.Random(4)
    for _ in range(400):
        res = lottery.draw_both(rookie, vet, rng=rng)
        assert res["rookie"][0] != "nabers"
        assert res["veteran"][0] != "later"


def test_no_sweep_guardrail_holds_across_a_long_run():
    res = lottery.simulate(rookie_drum(), vet_drum(), n=4000, seed=11)
    assert res["sweeps"] == 0


def test_turning_off_no_sweep_lets_a_team_take_both(monkeypatch):
    rules = dict(config.lottery_rules())
    rules["no_sweep"] = False
    monkeypatch.setattr(config, "lottery_rules", lambda: rules)
    res = lottery.simulate(rookie_drum(), vet_drum(), n=4000, seed=11)
    assert res["sweeps"] > 0, "without the guardrail one team does sweep sometimes"


def test_everything_is_locked_out_falls_back_rather_than_crashing():
    seats = rookie_drum(locked=[s.owner_id for s in rookie_drum()])
    order = lottery.draw(seats, rng=random.Random(2))
    assert len(order) == len(seats)


# ---------------------------------------------------------------- odds

def test_odds_track_ball_weights():
    res = lottery.simulate(rookie_drum(), vet_drum(), n=8000, seed=5)
    first = {o: row[0] for o, row in res["rookie"].items()}
    assert first["nabers"] > first["later"] > first["whig"] > first["taco"]
    assert first["nabers"] == pytest.approx(config.lottery_weights()[0], abs=2.0)


def test_champion_still_holds_a_live_ticket():
    res = lottery.simulate(rookie_drum(), vet_drum(), n=8000, seed=5)
    assert res["rookie"]["taco"][0] > 0.5, "nobody should be drawing dead"


def test_median_slot():
    assert lottery.median_slot([60, 20, 20]) == 1
    assert lottery.median_slot([10, 10, 80]) == 3


def test_first_season_order_is_a_flat_shuffle():
    ids = [s.owner_id for s in rookie_drum()]
    got = lottery.first_season_order(ids, seed=4)
    assert sorted(got) == sorted(ids)


# --------------------------------------------------------------------------
# one drum, from the consolidated draft on
# --------------------------------------------------------------------------

def _season(champ_rank=1):
    """Eight teams: owner i finished at final_rank ranks[i]."""
    ranks = [1, 3, 2, 4, 5, 6, 7, 8]
    return [{"owner_id": str(i), "wins": 12 - r, "final_rank": r, "champion": r == champ_rank}
            for i, r in enumerate(ranks)]


def test_one_drum_from_2027_and_two_before():
    from halfmen import config
    assert not config.single_drum(2026)
    assert config.single_drum(2027) and config.single_drum(2031)


def test_the_one_drum_is_final_standing_chase_teams_by_chase_finish():
    seats = lottery.build_single(_season())
    by = {s.owner_id: s.weight for s in seats}
    w = config.lottery_weights()
    # final_rank 8 = lost out of the Chase: most balls; 5 = won the Chase
    assert by["7"] == w[0] and by["4"] == w[3]
    # playoff teams by finish, champion floored
    assert by["0"] == w[-1] and by["2"] == w[-2] and by["1"] == w[-3] and by["3"] == w[-4]


def test_winning_the_chase_costs_balls():
    seats = {s.owner_id: s.weight for s in lottery.build_single(_season())}
    assert seats["4"] < seats["5"] < seats["6"] < seats["7"]


def test_the_flat_first_season_locks_nobody_out():
    assert lottery.locked_out_for(2027, "someone", 2026) == []


def test_after_that_last_years_first_choice_is_barred():
    assert lottery.locked_out_for(2028, "someone", 2027) == ["someone"]
    assert lottery.locked_out_for(2028, None, 2027) == []


def test_the_one_drum_simulation_tracks_weights():
    res = lottery.simulate_one(lottery.build_single(_season()), n=6000, seed=3)
    first = {o: row[0] for o, row in res["drum"].items()}
    assert first["7"] > first["4"] > first["3"] > first["0"]
    assert abs(sum(first.values()) - 100) < 0.01


def test_the_2027_draft_has_sixteen_rounds():
    from halfmen import config
    assert config.veteran_rounds(2027) == int(config.drafts()["consolidated_rounds"])
    assert config.veteran_rounds(2026) == 14


def test_the_recap_renders_a_png():
    from halfmen import recap
    png = recap.render(6, "7½ Men", [("a", "A", 120.0), ("b", "B", 90.0)],
                       [("Blowout", "A by 30.0", "120 over B")], footer="next week")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10000
