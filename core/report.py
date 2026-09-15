# core/report.py
import pandas as pd


from core.scoring import score_play_points, score_play


def _format_cell(row) -> str:
    name = row.get("second_name", f"#{row['player_id']}")
    team = row.get("team", "")
    pos = row.get("pos", "")
    pts = row["scored_points"] if pd.notna(row["scored_points"]) else 0
    marker = ""
    if row.get("captain"):
        marker = " (C)"
    elif row.get("vice_captain"):
        marker = " (V)"
    return f"{name} ({pos}, {team}){marker} {pts:.0f}"


def build_season_grid(picks: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame, chips: pd.DataFrame) -> pd.DataFrame:
    scored = score_play_points(picks, chips, stats)          # has scored_points per player/gw
    merged = scored.merge(names, on="player_id", how="left")

    pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    merged["pos_rank"] = merged["pos"].astype(str).map(pos_order).astype(int)

    merged = merged.sort_values(
        ["gw", "in_starting_11", "pos_rank", "player_id"],
        ascending=[True, False, True, True],
    )
    merged["slot"] = merged.groupby("gw").cumcount()
    merged["cell"] = merged.apply(_format_cell, axis=1)

    labels_series = (
        merged.drop_duplicates("slot")
        .set_index("slot")["in_starting_11"]
        .map({True: "Starting XI", False: "Bench"})
        .sort_index()
    )
    display_labels = labels_series.where(labels_series != labels_series.shift(), "")

    grid = merged.pivot(index="slot", columns="gw", values="cell")
    grid = grid.reindex(labels_series.index)
    grid.index = pd.Index(display_labels.values, name=None)
    grid.columns = [f"GW{gw}" for gw in grid.columns]
    grid.columns.name = None

    # --- summary rows, sourced from score_play, not recomputed here ---
    result = score_play(picks, chips, stats)
    gw_points = result["gw_points"]
    penalties = result["penalties"]
    running_total = result["net_points"].cumsum()

    chip_by_gw = chips.set_index("gw")["chip"] if not chips.empty else pd.Series(dtype="string")

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

    return pd.concat([grid, summary])


def print_season_grid(picks: pd.DataFrame, stats: pd.DataFrame, names: pd.DataFrame, chunk_size: int = 8) -> None:
    grid = build_season_grid(picks, stats, names)
    gws = grid.columns.tolist()

    for i in range(0, len(gws), chunk_size):
        chunk = grid[gws[i:i + chunk_size]]
        print(chunk.to_string())
        print()  # blank line between chunks

