import pandas as pd
from core.budget import compute_budget_timeline


def validate_team(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame) -> list[str]:
    errors = []

    merged = picks.merge(stats, on=["player_id", "gw"], how="left")
    chip_by_gw = chips.set_index("gw")["chip"].to_dict()

    for gw, group in merged.groupby("gw"):
        squad = group

        counts = squad["pos"].value_counts()
        required = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
        for pos, req in required.items():
            actual = counts.get(pos, 0)
            if actual != req:
                errors.append(f"GW{gw}: {actual} {pos} in squad, expected {req}")

        starters = squad[squad["in_starting_11"]]
        start_counts = starters["pos"].value_counts()

        gk_start = start_counts.get("GK", 0)
        def_start = start_counts.get("DEF", 0)
        mid_start = start_counts.get("MID", 0)
        fwd_start = start_counts.get("FWD", 0)

        if gk_start != 1:
            errors.append(f"GW{gw}: {gk_start} starting GK, expected exactly 1")
        if def_start < 3:
            errors.append(f"GW{gw}: {def_start} starting DEF, need at least 3")
        if mid_start < 3:
            errors.append(f"GW{gw}: {mid_start} starting MID, need at least 3")
        if fwd_start < 1:
            errors.append(f"GW{gw}: {fwd_start} starting FWD, need at least 1")

        chip = chip_by_gw.get(gw, "none")
        if chip != "uteam":
            team_counts = squad["team"].value_counts()
            over_limit = team_counts[team_counts > 3]
            for team, n in over_limit.items():
                errors.append(f"GW{gw}: {n} players from {team}, max 3")

    return errors


def validate_budget(picks, chips, stats, initial_budget: float = 100.0) -> list[str]:
    errors = []
    for e in compute_budget_timeline(picks, chips, stats, initial_budget):
        if e["cash_after"] < 0:
            label = " (uteam)" if e["temporary"] else ""
            errors.append(f"GW{e['gw']}{label}: budget exceeded, bank = {e['cash_after'] / 10:.1f}")
    return errors


def validate_play(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, initial_budget: float = 100.0) -> list[str]:
    """Run all structural/legality checks. Returns combined error list."""
    errors = []
    errors += validate_team(picks, chips, stats)
    errors += validate_budget(picks, chips, stats, initial_budget)
    return errors