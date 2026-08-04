"""Load config.yaml and expose it in small, typed-ish accessors.

Everything the engine branches on lives in the YAML so the rules can be
changed without touching code.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("HALFMEN_CONFIG", ROOT / "config.yaml"))
DATA_DIR = Path(os.environ.get("HALFMEN_DATA", ROOT / "data"))


@lru_cache(maxsize=1)
def load() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r") as fh:
        cfg = yaml.safe_load(fh)
    # YAML will happily parse a 19-digit Sleeper id as an int; keep them strings.
    cfg["managers"] = {str(k): v for k, v in cfg.get("managers", {}).items()}
    cfg["me"] = str(cfg.get("me", ""))
    cfg["league"]["id"] = str(cfg["league"]["id"])
    return cfg


def league() -> Dict[str, Any]:
    return load()["league"]


def league_id() -> str:
    return league()["id"]


def season() -> int:
    return int(league()["season"])


def is_first_season(yr: int = None) -> bool:
    yr = season() if yr is None else yr
    return yr <= int(league()["first_season"])


def drafts() -> Dict[str, Any]:
    return load()["drafts"]


def veteran_rounds(yr: int = None) -> int:
    d = drafts()
    if is_first_season(yr):
        return int(d.get("veteran_rounds_first_season", d["veteran_rounds"]))
    return int(d["veteran_rounds"])


def rookie_rounds() -> int:
    return int(drafts()["rookie_rounds"])


def rules() -> Dict[str, Any]:
    return load()["rules"]


def keeper_rules() -> Dict[str, Any]:
    return rules()["keepers"]


def rookie_rules() -> Dict[str, Any]:
    return rules()["rookie_keepers"]


def franchise_rules() -> Dict[str, Any]:
    return rules()["franchise"]


def taxi_rules() -> Dict[str, Any]:
    return rules()["taxi"]


def faab_rules() -> Dict[str, Any]:
    return rules()["faab"]


def lottery_rules() -> Dict[str, Any]:
    return rules()["lottery"]


def roster() -> Dict[str, Any]:
    return load()["roster"]


def active_roster_size() -> int:
    r = roster()
    return len(r["starters"]) + int(r["bench"])


def managers() -> Dict[str, Dict[str, str]]:
    return load()["managers"]


def manager(user_id: str) -> Dict[str, str]:
    return managers().get(str(user_id), {})


def manager_name(user_id: str) -> str:
    return manager(user_id).get("name") or f"Unknown ({user_id})"


def team_name(user_id: str) -> str:
    return manager(user_id).get("team") or manager_name(user_id)


def me() -> str:
    return load()["me"]


def palette() -> str:
    return load().get("theme", {}).get("default_palette", "lights_off")


def lottery_weights(alt: bool = False) -> List[int]:
    lr = lottery_rules()
    return list(lr["weights_alt"] if alt else lr["weights"])


def adp_sources() -> Dict[str, Any]:
    return load().get("adp_sources", {})
