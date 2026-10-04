import pulp
import pandas as pd


def build_keys(stats: pd.DataFrame) -> list[tuple[int, int]]:
    return list(stats[["player_id", "gw"]].itertuples(index=False, name=None))


def build_lookups(stats: pd.DataFrame) -> dict:
    price = stats.set_index(["player_id", "gw"])["price"].to_dict()
    price_tenths = {k: round(v * 10) for k, v in price.items()}
    return {
        "points": stats.set_index(["player_id", "gw"])["points"].to_dict(),
        "pos": stats.set_index(["player_id", "gw"])["pos"].to_dict(),
        "team": stats.set_index(["player_id", "gw"])["team"].to_dict(),
        "price": price,
        "price_tenths": price_tenths,
    }


def build_selection_variables(keys: list[tuple[int, int]]) -> dict:
    """Squad, starting 11 and captaincy, per player and gameweek."""
    return {
        name: {k: pulp.LpVariable(f"{name}_{k[0]}_{k[1]}", cat="Binary") for k in keys}
        for name in ["permanent", "fielded", "start", "captain", "vice"]
    }


def build_budget_variables(keys: list[tuple[int, int]], gws, lookups: dict) -> dict:
    """Buying, selling, prices and bank balance (all money in tenths)."""
    price = lookups["price_tenths"]

    player_prices = {}
    for (p, w), pr in price.items():
        player_prices.setdefault(p, []).append(pr)

    price_bounds = {p: (min(prices), max(prices)) for p, prices in player_prices.items()}

    buy = {k: pulp.LpVariable(f"buy_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    sell = {k: pulp.LpVariable(f"sell_{k[0]}_{k[1]}", cat="Binary") for k in keys}

    bought_price = {}
    sale_proceeds = {}
    sale_proceeds_actual = {}
    for k in keys:
        p, w = k
        lo, hi = price_bounds[p]

        bought_price[k] = pulp.LpVariable(f"bought_price_{p}_{w}", lowBound=lo, upBound=hi, cat="Integer")
        sale_proceeds[k] = pulp.LpVariable(f"sale_proceeds_{p}_{w}", lowBound=0, upBound=hi, cat="Integer")
        sale_proceeds_actual[k] = pulp.LpVariable(f"sale_proceeds_actual_{p}_{w}", lowBound=0, upBound=hi, cat="Integer")

    bank = {w: pulp.LpVariable(f"bank_{w}", lowBound=0, cat="Integer") for w in gws}

    # what each held player puts towards the Loan rangers budget
    uteam_credit = {
        k: pulp.LpVariable(f"uteam_credit_{k[0]}_{k[1]}", lowBound=0, upBound=price[k], cat="Integer")
        for k in keys
    }

    return {
        "buy": buy,
        "sell": sell,
        "bought_price": bought_price,
        "sale_proceeds": sale_proceeds,
        "sale_proceeds_actual": sale_proceeds_actual,
        "bank": bank,
        "uteam_credit": uteam_credit,
    }


def build_transfer_variables(gws, max_banked: int = 5) -> dict:
    gws_sorted = sorted(gws)

    banked = {w: pulp.LpVariable(f"banked_{w}", lowBound=0, upBound=max_banked, cat="Integer") for w in gws_sorted}
    extra = {w: pulp.LpVariable(f"extra_transfers_{w}", lowBound=0, cat="Integer") for w in gws_sorted}

    return {"banked": banked, "extra": extra}


def build_chip_variables(keys: list[tuple[int, int]], gws) -> dict:
    """One flag per chip and gameweek, plus the per-player helpers that linearize the chip bonuses."""
    flags = {
        "2capt": {w: pulp.LpVariable(f"2capt_{w}", cat="Binary") for w in gws},
        "pdbus": {w: pulp.LpVariable(f"chippdbus_{w}", cat="Binary") for w in gws},
        "wildcard": {w: pulp.LpVariable(f"chipwildcard_{w}", cat="Binary") for w in gws},
        "uteam": {w: pulp.LpVariable(f"chiputeam_{w}", cat="Binary") for w in gws},
    }
    helpers = {
        name: {k: pulp.LpVariable(f"{name}_{k[0]}_{k[1]}", cat="Binary") for k in keys}
        for name in [
            "cap_2c",       # captain on a Dynamic duo week
            "vice_2c",      # vice captain on a Dynamic duo week
            "start_pdbus",  # starter on a Park the bus week
            "cap_pdbus",    # captain on a Park the bus week (loses the captain bonus)
        ]
    }
    return flags | helpers
