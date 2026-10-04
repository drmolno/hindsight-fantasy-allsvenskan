# core/report.py
from itertools import zip_longest

import pandas as pd

from core.budget import compute_budget_timeline
from core.scoring import score_play_points, score_play

POS_ORDER = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
CHIP_NAMES = {"pdbus": "Park the bus", "wildcard": "Wildcard", "uteam": "Loan rangers", "2capt": "Dynamic duo"}


def _format_cell(row) -> str:
    name = row.get("second_name", f"#{row['player_id']}")
    team = row.get("team", "")
    pos = row.get("pos", "")
    marker = ""
    if row.get("captain"):
        marker = " (C)"
    elif row.get("vice_captain"):
        marker = " (V)"
    if not row["in_starting_11"]:
        # bench points don't count towards the game week, so show them in parentheses
        pts = row["points"] if pd.notna(row["points"]) else 0
        return f"{name} ({pos}, {team}){marker} ({pts:.0f})"
    pts = row["scored_points"] if pd.notna(row["scored_points"]) else 0
    return f"{name} ({pos}, {team}){marker} {pts:.0f}"


def build_season_grid(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    scored = score_play_points(picks, chips, stats)          # has scored_points per player/gw
    merged = scored.merge(names, on="player_id", how="left")

    merged["pos_rank"] = merged["pos"].astype(str).map(POS_ORDER).astype(int)

    merged = merged.sort_values(
        ["gw", "in_starting_11", "pos_rank", "player_id"],
        ascending=[True, False, True, True],
    )
    merged["slot"] = merged.groupby("gw").cumcount()
    merged["cell"] = merged.apply(_format_cell, axis=1)

    labels_series = (
        merged.drop_duplicates("slot")
        .set_index("slot")["in_starting_11"]
        .map({True: "Starting 11", False: "Bench"})
        .sort_index()
    )
    display_labels = labels_series.where(labels_series != labels_series.shift(), "")

    grid = merged.pivot(index="slot", columns="gw", values="cell")
    grid = grid.reindex(labels_series.index)
    grid.index = pd.Index(display_labels.values, name=None)
    grid.columns = [f"GW{gw}" for gw in grid.columns]
    grid.columns.name = None

    # formation from the starters' outfield positions, e.g. "4-4-2"
    starter_counts = (
        merged[merged["in_starting_11"]]
        .assign(pos=lambda d: d["pos"].astype(str))
        .groupby(["gw", "pos"]).size().unstack(fill_value=0)
    )
    formation = pd.DataFrame(
        [[f"{starter_counts.loc[gw].get('DEF', 0)}-{starter_counts.loc[gw].get('MID', 0)}-{starter_counts.loc[gw].get('FWD', 0)}"
          for gw in starter_counts.index]],
        index=["Formation"], columns=[f"GW{gw}" for gw in starter_counts.index],
    ).reindex(columns=grid.columns, fill_value="")

    # --- summary rows, sourced from score_play, not recomputed here ---
    result = score_play(picks, chips, stats)
    gw_points = result["gw_points"]
    penalties = result["penalties"]
    running_total = result["net_points"].cumsum()

    chip_by_gw = chips.set_index("gw")["chip"].map(lambda c: CHIP_NAMES.get(c, c)) if not chips.empty else pd.Series(dtype="string")

    def _relabel(s):
        s = s.copy()
        s.index = [f"GW{gw}" for gw in s.index]
        return s

    summary = pd.DataFrame(
        [_relabel(gw_points).reindex(grid.columns, fill_value=0).astype(int),
         _relabel(penalties).reindex(grid.columns, fill_value=0).astype(int),
         _relabel(running_total).reindex(grid.columns, fill_value=0).astype(int),
         _relabel(chip_by_gw).reindex(grid.columns, fill_value="")],
        index=["Game week points", "Transfer penalty", "Running total", "Chip"],
    )

    extras = build_budget_rows(compute_budget_timeline(picks, chips, stats), stats, names)
    extras.columns = [f"GW{w}" for w in extras.columns]
    extras = extras.reindex(columns=grid.columns, fill_value="")
    
    return pd.concat([formation, grid, summary, extras])


def _pair_transfers(sold: list[tuple], bought: list[tuple], pos_of: dict) -> list[tuple]:
    """Pair each sold player with a bought player in the same position.
    Pairs run GK -> DEF -> MID -> FWD, most expensive first within a position."""
    pairs = []
    for pos in POS_ORDER:
        outs = sorted((t for t in sold if pos_of.get(t[0]) == pos), key=lambda t: -t[1])
        ins = sorted((t for t in bought if pos_of.get(t[0]) == pos), key=lambda t: -t[1])
        pairs += list(zip_longest(outs, ins))
    return pairs


def build_budget_rows(timeline: list[dict], stats: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    name_of = names.set_index("player_id")["second_name"].to_dict()
    pos_of = stats.groupby("player_id")["pos"].first().astype(str).to_dict()

    def fmt_in(t):
        return f"{name_of.get(t[0], t[0])} {t[1] / 10:.1f}" if t else "–"

    def fmt_out(t):
        if not t:
            return "–"
        pid, proceeds, bought_price = t
        return f"{name_of.get(pid, pid)} {proceeds / 10:.1f} (bought {bought_price / 10:.1f}, {(proceeds - bought_price) / 10:+.1f})"

    rows = {
        "Squad value": {e["gw"]: f"{e['squad_value'] / 10:.1f}" for e in timeline},
        "Bank balance":        {e["gw"]: f"{e['bank'] / 10:.1f}" for e in timeline},
        # realised profit on sales; temporary uteam sales are reverted, so they don't count
        #"Sale profit": {
        #    e["gw"]: f"{sum(proceeds - bp for _, proceeds, bp in e['sold']) / 10:+.1f}" if e["sold"] and not e["temporary"] else ""
        #    for e in timeline
        #},
    }

    lines_by_gw = {}
    for e in timeline:
        tag = "*" if e["temporary"] else ""   # * marks temporary uteam swaps
        pairs = _pair_transfers(e["sold"], e["bought"], pos_of)
        lines_by_gw[e["gw"]] = [f"{fmt_out(out)} → {fmt_in(inn)}{tag}" for out, inn in pairs]

    n_rows = max((len(l) for l in lines_by_gw.values()), default=0)
    for i in range(n_rows):
        rows[f"Transfer {i + 1}"] = {
            gw: (lines[i] if i < len(lines) else "") for gw, lines in lines_by_gw.items()
        }
    budget = pd.DataFrame(rows).T
    # show "Transfers" on the first transfer row only, blank labels after it
    budget.index = [
        ("Transfers" if label == "Transfer 1" else "") if label.startswith("Transfer ") else label
        for label in budget.index
    ]
    return budget


def _scored_picks(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    scored = score_play_points(picks, chips, stats).merge(names, on="player_id", how="left")
    scored["pos"] = scored["pos"].astype(str)
    scored["team"] = scored["team"].astype(str)
    return scored


def player_contributions(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """One row per player used: points contributed (incl. captain and chip bonuses), starts, captaincies."""
    scored = _scored_picks(picks, chips, stats, names)
    contrib = scored.groupby("player_id").agg(
        name=("second_name", "first"),
        pos=("pos", "first"),
        team=("team", "first"),
        points=("scored_points", "sum"),
        starts=("in_starting_11", "sum"),
        captain=("captain", "sum"),
        squad_weeks=("gw", "nunique"),
    )
    return contrib.astype({"points": int, "starts": int, "captain": int}).sort_values("points", ascending=False)


def position_summary(contrib: pd.DataFrame) -> pd.DataFrame:
    """Points per position and the top contributor in each, plus a total row with the overall top player."""
    rows = []
    groups = [(pos, contrib[contrib["pos"] == pos]) for pos in POS_ORDER] + [("Total", contrib)]
    for label, group in groups:
        top = group.iloc[0]  # contrib is sorted by points
        rows.append({
            "Position": label,
            "Points": group["points"].sum(),
            "Players used": len(group),
            "Top player": f"{top['name']} ({top['team']})" if label != "Total" else f"{top['name']} ({top['pos']}, {top['team']})",
            "Top player points": top["points"],
            "Starts": top["starts"],
            "Captain": top["captain"],
        })
    return pd.DataFrame(rows)


def club_summary(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Clubs ranked by points contributed. Points count for the club the player belonged to that week."""
    scored = _scored_picks(picks, chips, stats, names)
    per_player = (
        scored.groupby(["team", "player_id"])
        .agg(name=("second_name", "first"), pos=("pos", "first"), points=("scored_points", "sum"), starts=("in_starting_11", "sum"))
        .reset_index()
        .sort_values("points", ascending=False)
    )

    rows = []
    for club in sorted(stats["team"].astype(str).unique()):
        group = per_player[per_player["team"] == club]
        top = group.iloc[0] if len(group) else None
        rows.append({
            "Club": club,
            "Points": int(group["points"].sum()),
            "Players used": len(group),
            "Starts": int(group["starts"].sum()),
            "Top player": f"{top['name']} ({top['pos']})" if top is not None else "–",
            "Top player points": int(top["points"]) if top is not None else 0,
        })

    clubs = pd.DataFrame(rows).sort_values(["Points", "Club"], ascending=[False, True])
    clubs.insert(0, "Rank", range(1, len(clubs) + 1))
    return clubs


def print_season_grid(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame, chunk_size: int = 8) -> None:
    grid = build_season_grid(picks, chips, stats, names)
    gws = grid.columns.tolist()

    for i in range(0, len(gws), chunk_size):
        chunk = grid[gws[i:i + chunk_size]]
        print(chunk.to_string())
        print()  # blank line between chunks

