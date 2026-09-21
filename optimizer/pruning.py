import pandas as pd

def find_dominated_players(stats: pd.DataFrame) -> set[int]:
    """Return player_ids that are dominated by another player: same position, same team,
    at least as expensive every week, and scores no more in any week they both appear."""

    # wide format: one row per player, one column per gw, for points and price
    points_wide = stats.pivot(index="player_id", columns="gw", values="points")
    price_wide = stats.pivot(index="player_id", columns="gw", values="price")

    meta = stats.groupby("player_id").agg(pos=("pos", "first"), team=("team", "first"))

    dominated = set()

    for (pos, team), group in meta.groupby(["pos", "team"]):
        player_ids = group.index.tolist()

        for a in player_ids:
            if a in dominated:
                continue
            for b in player_ids:
                if a == b or b in dominated:
                    continue

                # compare only on weeks both players have data for
                common_gws = points_wide.columns[
                    points_wide.loc[a].notna() & points_wide.loc[b].notna()
                ]
                if len(common_gws) == 0:
                    continue

                a_points = points_wide.loc[a, common_gws]
                b_points = points_wide.loc[b, common_gws]
                a_price = price_wide.loc[a, common_gws]
                b_price = price_wide.loc[b, common_gws]

                # does b dominate a? b >= a in points every week, b <= a in price every week,
                # with at least one strict inequality (otherwise they're identical, arbitrary tie-break)
                at_least_as_good = (b_points >= a_points).all() and (b_price <= a_price).all()
                strictly_better = (b_points > a_points).any() or (b_price < a_price).any()

                if at_least_as_good and strictly_better:
                    dominated.add(a)
                    break  # a is dominated, no need to check further

    return dominated
