"""Who the table has already decided: clinched, or out."""
from halfmen import playoffs


def _rows(wins, results):
    return [{"owner_id": str(i), "wins": w, "results": results} for i, w in enumerate(wins)]


def test_early_season_decides_nobody():
    assert playoffs.locks(_rows([10, 8, 7, 7, 6, 4, 4, 2], 12), 4, 28) == {}


def test_a_team_four_teams_have_passed_for_good_is_out():
    # 2 results left each: the last team tops out at 4, four teams already have 5+;
    # the 13-win team can still reach 15 and pass the 14-win team
    out = playoffs.locks(_rows([20, 18, 16, 14, 13, 6, 4, 2], 26), 4, 28)
    assert out["7"] == "out" and out["6"] == "out" and "4" not in out and "3" not in out


def test_a_team_no_more_than_three_can_catch_is_in():
    out = playoffs.locks(_rows([20, 18, 16, 14, 9, 6, 4, 2], 26), 4, 28)
    assert out["0"] == "in" and out["1"] == "in"


def test_a_tie_on_wins_still_leaves_the_door_open():
    # the 5th team can reach exactly the 4th team's wins: neither is decided
    out = playoffs.locks(_rows([20, 18, 16, 14, 12, 3, 2, 1], 26), 4, 28)
    assert "3" not in out and "4" not in out
