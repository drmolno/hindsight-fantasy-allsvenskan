import pandas as pd


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


def sale_price(bought_price: int, current_price: int) -> int:
    """Compute sale price in tenths, given bought and current price in tenths.
    Profit: bought + floor(profit / 2). Loss: full loss, i.e. current price."""
    profit = current_price - bought_price
    if profit > 0:
        return bought_price + profit // 2
    else:
        return current_price


def validate_budget(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, initial_budget: float = 100.0) -> list[str]:
    errors = []
    price_lookup = stats.set_index(["player_id", "gw"])["price"].to_dict()
    chip_by_gw = chips.set_index("gw")["chip"].to_dict()

    gws = sorted(picks["gw"].unique())
    bought_price = {}
    bank = round(initial_budget * 10)

    permanent_squad = None

    for gw in gws:
        squad = set(picks.loc[picks["gw"] == gw, "player_id"])
        chip = chip_by_gw.get(gw, "none")

        if chip == "uteam":
            sold = permanent_squad - squad
            bought = squad - permanent_squad

            temp_bank = bank
            for pid in sold:
                current_price = round(price_lookup[(pid, gw)] * 10)
                temp_bank += sale_price(bought_price[pid], current_price)
            for pid in bought:
                price = round(price_lookup[(pid, gw)] * 10)
                temp_bank -= price

            if temp_bank < 0:
                errors.append(f"GW{gw} (uteam): budget exceeded, bank = {temp_bank / 10:.1f}")

        elif permanent_squad is None:
            cost = 0
            for pid in squad:
                price = round(price_lookup[(pid, gw)] * 10)
                bought_price[pid] = price
                cost += price
            bank -= cost

            if bank < 0:
                errors.append(f"GW{gw}: budget exceeded, bank = {bank / 10:.1f}")

            permanent_squad = squad

        else:
            sold = permanent_squad - squad
            bought = squad - permanent_squad

            for pid in sold:
                
                current_price = round(price_lookup[(pid, gw)] * 10)
                bank += sale_price(bought_price[pid], current_price)
                del bought_price[pid]

            for pid in bought:
                price = round(price_lookup[(pid, gw)] * 10)
                bought_price[pid] = price
                bank -= price

            if bank < 0:
                print(f"Bank is {bank}")
                errors.append(f"GW{gw}: budget exceeded, bank = {bank / 10:.1f}")

            permanent_squad = squad

    return errors


def validate_play(picks: pd.DataFrame, chips: pd.DataFrame, stats: pd.DataFrame, initial_budget: float = 100.0) -> list[str]:
    """Run all structural/legality checks. Returns combined error list."""
    errors = []
    errors += validate_team(picks, chips, stats)
    errors += validate_budget(picks, chips, stats, initial_budget)
    return errors