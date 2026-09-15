import pandas as pd


def score_play_points(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    merged = picks.merge(stats, on=["player_id", "gw"], how="left")
    merged = merged.merge(chips, on="gw", how="left")
    merged["chip"] = merged["chip"].fillna("none")

    merged["scored_points"] = merged["points"] * merged["in_starting_11"]

    is_pdbus = merged["chip"] == "pdbus"
    is_2capt = merged["chip"] == "2capt"

    # captain / vice multipliers — no captaincy bonus at all on pdbus weeks
    merged.loc[merged["captain"] & ~is_2capt & ~is_pdbus, "scored_points"] *= 2
    merged.loc[merged["captain"] & is_2capt, "scored_points"] *= 3
    merged.loc[merged["vice_captain"] & is_2capt, "scored_points"] *= 2

    # pdbus: all starting defenders score double
    is_defender = merged["pos"] == "DEF"
    merged.loc[is_pdbus & is_defender & merged["in_starting_11"], "scored_points"] *= 2
    
    return merged


def transfer_penalty(
    picks: pd.DataFrame,
    chips: pd.DataFrame,
    initial_free_transfers: int = 1,
    max_banked: int = 5,
) -> pd.Series:
    gws = sorted(picks["gw"].unique())
    chip_by_gw = chips.set_index("gw")["chip"].to_dict()

    penalties = {}
    banked = initial_free_transfers
    permanent_squad = None

    for gw in gws:
        squad = set(picks.loc[picks["gw"] == gw, "player_id"])
        chip = chip_by_gw.get(gw, "none")

        if chip in ("wildcard", "uteam"):
            penalties[gw] = 0

        elif permanent_squad is None:
            penalties[gw] = 0

        else:
            transfers = len(squad - permanent_squad)
            extra = max(0, transfers - banked)
            penalties[gw] = extra * 4
            leftover = max(0, banked - transfers)
            banked = min(leftover + 1, max_banked)

        if chip != "uteam":
            permanent_squad = squad

    return pd.Series(penalties, name="transfer_penalty")


def score_play(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, free_transfers: int = 1) -> dict:
    scored = score_play_points(picks, chips, stats)
    gw_points = scored.groupby("gw")["scored_points"].sum()

    penalties = transfer_penalty(picks, chips, free_transfers)
    net_points = gw_points - penalties

    return {
        "gw_points": gw_points,
        "penalties": penalties,
        "net_points": net_points,
        "total": net_points.sum(),
    }
