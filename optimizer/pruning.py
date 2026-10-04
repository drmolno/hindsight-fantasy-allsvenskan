import pandas as pd


def prune_by_score_per_price(stats: pd.DataFrame, threshold: float = -10):
    mask = stats["points"] / stats["price"] < threshold
    return set(stats.loc[mask, ["player_id", "gw"]].itertuples(index=False, name=None))


def prune_by_score(stats: pd.DataFrame, threshold: float = -10):
    mask = stats["points"] < threshold
    return set(stats.loc[mask, ["player_id", "gw"]].itertuples(index=False, name=None))


def prune_by_three_score_per_price(stats: pd.DataFrame, threshold: float = -10) -> set[tuple[int, int]]:
    ratio = stats["points"] / stats["price"]
    stats = stats.assign(low=ratio < threshold)

    wide = stats.pivot(index="player_id", columns="gw", values="low")
    wide = wide.sort_index(axis=1)

    prev_low = wide.shift(1, axis=1)
    next_low = wide.shift(-1, axis=1)
    prune_mask = wide & prev_low & next_low

    pruned = prune_mask.stack()
    pruned = pruned[pruned]

    return set(pruned.index)


def prune_by_clubs(stats: pd.DataFrame, clubs: str | list[str]) -> set[tuple[int, int]]:
    """Prune every (player, gw) where the player plays for one of the given clubs that week."""
    if isinstance(clubs, str):
        clubs = [clubs]

    unknown = set(clubs) - set(stats["team"].astype(str))
    if unknown:
        raise ValueError(f"Unknown club(s): {sorted(unknown)}. Valid names: {sorted(stats['team'].astype(str).unique())}")

    mask = stats["team"].astype(str).isin(clubs)
    return set(stats.loc[mask, ["player_id", "gw"]].itertuples(index=False, name=None))