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
    permanent = {k: pulp.LpVariable(f"permanent_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    fielded = {k: pulp.LpVariable(f"fielded_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    start = {k: pulp.LpVariable(f"start_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    return {"permanent": permanent, "fielded": fielded, "start": start}


def build_budget_variables(keys: list[tuple[int, int]], gws, lookups: dict) -> dict:
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

    #big_m = {p: max(hi - lo, 1) for p, (lo, hi) in price_bounds.items()}   

    return {
        "buy": buy,
        "sell": sell,
        "bought_price": bought_price,
        "sale_proceeds": sale_proceeds,
        "sale_proceeds_actual": sale_proceeds_actual,
        "bank": bank,
        #"big_m": big_m,
    }


def build_transfer_variables(gws, max_banked: int = 5) -> dict:
    gws_sorted = sorted(gws)

    banked = {w: pulp.LpVariable(f"banked_{w}", lowBound=0, upBound=max_banked, cat="Integer") for w in gws_sorted}
    extra = {w: pulp.LpVariable(f"extra_transfers_{w}", lowBound=0, cat="Integer") for w in gws_sorted}
    leftover = {w: pulp.LpVariable(f"leftover_{w}", lowBound=0, upBound=max_banked, cat="Integer") for w in gws_sorted}
    over_zero = {w: pulp.LpVariable(f"over_zero_{w}", cat="Binary") for w in gws_sorted}

    return {"banked": banked, "extra": extra, "leftover": leftover, "over_zero": over_zero}


def build_captain_variables(keys: list[tuple[int, int]]) -> dict:
    captain = {k: pulp.LpVariable(f"captain_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    vice = {k: pulp.LpVariable(f"vice_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    return {"captain": captain, "vice": vice}


def build_chip_variables(gws) -> dict:
    two_capt = {w: pulp.LpVariable(f"2capt_{w}", cat="Binary") for w in gws}
    return {"2capt": two_capt}


def build_dynamic_duo_linearization_variables(keys: list[tuple[int, int]]) -> dict:
    cap_2c = {k: pulp.LpVariable(f"cap_2c_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    vice_2c = {k: pulp.LpVariable(f"vice_2c_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    return {"cap_2c": cap_2c, "vice_2c": vice_2c}


def build_pdbus_variables(gws) -> dict:
    pdbus = {w: pulp.LpVariable(f"chippdbus_{w}", cat="Binary") for w in gws}
    return {"pdbus": pdbus}


def build_pdbus_linearization_variables(keys: list[tuple[int, int]]) -> dict:
    start_pdbus = {k: pulp.LpVariable(f"start_pdbus_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    return {"start_pdbus": start_pdbus}


def build_pdbus_captain_suppression_variables(keys: list[tuple[int, int]]) -> dict:
    cap_pdbus = {k: pulp.LpVariable(f"cap_pdbus_{k[0]}_{k[1]}", cat="Binary") for k in keys}
    return {"cap_pdbus": cap_pdbus}


def build_wildcard_variables(gws) -> dict:
    wildcard = {w: pulp.LpVariable(f"chipwildcard_{w}", cat="Binary") for w in gws}
    return {"wildcard": wildcard}


def build_uteam_variables(gws) -> dict:
    uteam = {w: pulp.LpVariable(f"chiputeam_{w}", cat="Binary") for w in gws}
    return {"uteam": uteam}


def build_uteam_budget_variables(keys, lookups) -> dict:
    price = lookups["price_tenths"]
    sale_value_if_held = {
        k: pulp.LpVariable(f"sale_value_if_held_{k[0]}_{k[1]}", lowBound=0, upBound=price[k], cat="Integer")
        for k in keys
    }
    return {"sale_value_if_held": sale_value_if_held}