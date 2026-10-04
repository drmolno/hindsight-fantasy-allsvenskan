import pulp


def _keys_by_gw(keys) -> dict:
    by_gw = {}
    for k in keys:
        by_gw.setdefault(k[1], []).append(k)
    return by_gw


def _gws_by_player(keys) -> dict:
    """player_id -> sorted list of the gws that player appears in."""
    by_player = {}
    for p, w in keys:
        by_player.setdefault(p, []).append(w)
    return {p: sorted(ws) for p, ws in by_player.items()}


def add_squad_start_link(prob, keys, variables):
    fielded, start = variables["fielded"], variables["start"]
    for k in keys:
        prob += start[k] <= fielded[k] 


def add_squad_composition(prob, keys, variables, lookups, gws):
    fielded = variables["fielded"]
    pos = lookups["pos"]
    required = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    keys_by_gw = _keys_by_gw(keys)

    for w in gws:
        keys_w = keys_by_gw[w]
        for p, req in required.items():
            prob += pulp.lpSum(fielded[k] for k in keys_w if pos[k] == p) == req


def add_formation(prob, keys, variables, lookups, gws):
    start = variables["start"]
    pos = lookups["pos"]
    keys_by_gw = _keys_by_gw(keys)

    for w in gws:
        keys_w = keys_by_gw[w]
        prob += pulp.lpSum(start[k] for k in keys_w) == 11
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "GK") == 1
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "DEF") >= 3
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "MID") >= 3
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "FWD") >= 1


def add_team_limit(prob, keys, variables, lookups, gws, max_per_team: int = 3):
    fielded = variables["fielded"]
    team = lookups["team"]
    uteam = variables["uteam"]
    M = 15 - max_per_team  # relax up to the full squad size, no further
    keys_by_gw = _keys_by_gw(keys)

    for w in gws:
        keys_w = keys_by_gw[w]
        teams_w = {team[k] for k in keys_w}
        for t in teams_w:
            prob += pulp.lpSum(fielded[k] for k in keys_w if team[k] == t) <= max_per_team + M * uteam[w]
            

def add_buy_sell_link(prob, keys, variables):
    permanent = variables["permanent"]
    buy = variables["buy"]
    sell = variables["sell"]

    for p, player_gws_sorted in _gws_by_player(keys).items():
        for i, w in enumerate(player_gws_sorted):
            k = (p, w)
            if i == 0:
                prob += buy[k] == permanent[k]
                prob += sell[k] == 0
            else:
                w_prev = player_gws_sorted[i - 1]
                k_prev = (p, w_prev)
                prob += permanent[k] - permanent[k_prev] == buy[k] - sell[k]
                prob += buy[k] + sell[k] <= 1


def add_bought_price_tracking(prob, keys, variables, lookups):
    permanent = variables["permanent"]
    buy = variables["buy"]
    bought_price = variables["bought_price"]
    
    price = lookups["price_tenths"]

    for p, player_gws_sorted in _gws_by_player(keys).items():
        for i, w in enumerate(player_gws_sorted):
            k = (p, w)

            prices_so_far = [price[(p, w2)] for w2 in player_gws_sorted[:i+1]]
            lo_w, hi_w = min(prices_so_far), max(prices_so_far)
            m_lower = price[k]-lo_w
            m_upper = hi_w - price[k]
            prob += bought_price[k] >= price[k] - m_lower * (1 - buy[k])
            prob += bought_price[k] <= price[k] + m_upper * (1 - buy[k])

            if i > 0:
                w_prev = player_gws_sorted[i - 1]
                k_prev = (p, w_prev)
                m_carry = hi_w-lo_w
                prob += bought_price[k] >= bought_price[k_prev] - m_carry * (buy[k] + (1 - permanent[k_prev]))
                prob += bought_price[k] <= bought_price[k_prev] + m_carry * (buy[k] + (1 - permanent[k_prev]))

def add_sale_proceeds(prob, keys, variables, lookups):
    """sale_proceeds = min(current_price, (bought_price + current_price) / 2) — concave, no big-M needed."""
    bought_price = variables["bought_price"]
    sale_proceeds = variables["sale_proceeds"]
    price = lookups["price_tenths"]

    for k in keys:
        prob += sale_proceeds[k] <= price[k]
        prob += 2 * sale_proceeds[k] <= bought_price[k] + price[k]


def add_bank_balance(prob, keys, variables, lookups, gws, initial_budget: float = 100.0):
    buy = variables["buy"]
    sale_proceeds_actual = variables["sale_proceeds_actual"]
    bank = variables["bank"]
    price = lookups["price_tenths"]

    initial_budget_tenths = round(initial_budget * 10)

    keys_by_gw = _keys_by_gw(keys)
    gws_sorted = sorted(gws)

    for i, w in enumerate(gws_sorted):
        keys_w = keys_by_gw[w]
        spent = pulp.lpSum(price[k] * buy[k] for k in keys_w)
        earned = pulp.lpSum(sale_proceeds_actual[k] for k in keys_w)

        if i == 0:
            prob += bank[w] == initial_budget_tenths - spent
        else:
            w_prev = gws_sorted[i - 1]
            prob += bank[w] == bank[w_prev] + earned - spent


def add_sale_proceeds_linearization(prob, keys, variables, lookups):
    """sale_proceeds_actual = sale_proceeds * sell, linearized (continuous x binary)."""
    sale_proceeds = variables["sale_proceeds"]
    sale_proceeds_actual = variables["sale_proceeds_actual"]
    sell = variables["sell"]
    price = lookups["price_tenths"]

    for k in keys:
        hi = price[k] 
        prob += sale_proceeds_actual[k] <= sale_proceeds[k]
        prob += sale_proceeds_actual[k] <= hi * sell[k]
        prob += sale_proceeds_actual[k] >= sale_proceeds[k] - hi * (1 - sell[k])


def add_transfer_penalty(prob, keys, variables, gws, initial_free_transfers: int = 1, max_banked: int = 5, big_m_transfers: int = 16):
    buy = variables["buy"]
    banked = variables["banked"]
    extra = variables["extra"]
    wildcard = variables["wildcard"]
    uteam = variables["uteam"]

    gws_sorted = sorted(gws)
    keys_by_gw = _keys_by_gw(keys)

    for i, w in enumerate(gws_sorted):
        transfers_used = pulp.lpSum(buy[k] for k in keys_by_gw[w])

        if i == 0:
            # the initial squad is free and no transfers are banked from it
            prob += banked[w] == initial_free_transfers
            prob += extra[w] == 0
            if i + 1 < len(gws_sorted):
                prob += banked[gws_sorted[i + 1]] == initial_free_transfers
            continue

        freeze = wildcard[w] + uteam[w]

        prob += extra[w] >= transfers_used - banked[w] - big_m_transfers * freeze

        if i + 1 < len(gws_sorted):
            w_next = gws_sorted[i + 1]
            # Only upper bounds: more banked transfers is never worse, so the solver pushes banked up to them.
            # Normal week: banked - transfers + extra = max(0, banked - transfers), and upBound caps banked at max_banked.
            prob += banked[w_next] <= banked[w] - transfers_used + extra[w] + 1 + big_m_transfers * freeze
            # Wildcard / uteam week: banked carries over unchanged
            prob += banked[w_next] <= banked[w] + max_banked * (1 - freeze)


def add_captain_constraints(prob, keys, variables, gws):
    start = variables["start"]
    captain = variables["captain"]
    vice = variables["vice"]

    for k in keys:
        prob += captain[k] <= start[k]   # can only captain a starter
        prob += vice[k] <= start[k]      # same for vice
        prob += captain[k] + vice[k] <= 1  # can't be both

    keys_by_gw = _keys_by_gw(keys)
    for w in gws:
        keys_w = keys_by_gw[w]
        prob += pulp.lpSum(captain[k] for k in keys_w) == 1
        prob += pulp.lpSum(vice[k] for k in keys_w) == 1


def add_dynamic_duo_linearization(prob, keys, variables):
    captain = variables["captain"]
    vice = variables["vice"]
    two_capt = variables["2capt"]
    cap_2c = variables["cap_2c"]
    vice_2c = variables["vice_2c"]

    for k in keys:
        p, w = k

        prob += cap_2c[k] <= captain[k]
        prob += cap_2c[k] <= two_capt[w]
        prob += cap_2c[k] >= captain[k] + two_capt[w] - 1

        prob += vice_2c[k] <= vice[k]
        prob += vice_2c[k] <= two_capt[w]
        prob += vice_2c[k] >= vice[k] + two_capt[w] - 1


def add_chip_usage_limit(prob, gws, variables, chip_name: str, max_uses: int = 1):
    chip = variables[chip_name]
    prob += pulp.lpSum(chip[w] for w in gws) <= max_uses


def add_pdbus_linearization(prob, keys, variables):
    start = variables["start"]
    pdbus = variables["pdbus"]
    start_pdbus = variables["start_pdbus"]

    for k in keys:
        p, w = k
        prob += start_pdbus[k] <= start[k]
        prob += start_pdbus[k] <= pdbus[w]
        prob += start_pdbus[k] >= start[k] + pdbus[w] - 1


def add_pdbus_captain_suppression(prob, keys, variables):
    captain = variables["captain"]
    pdbus = variables["pdbus"]
    cap_pdbus = variables["cap_pdbus"]

    for k in keys:
        p, w = k
        prob += cap_pdbus[k] <= captain[k]
        prob += cap_pdbus[k] <= pdbus[w]
        prob += cap_pdbus[k] >= captain[k] + pdbus[w] - 1


def add_chip_exclusivity(prob, gws, variables, chip_names: list[str]):
    for w in gws:
        prob += pulp.lpSum(variables[name][w] for name in chip_names) <= 1


def add_wildcard_window_limits(prob, variables, first_half=range(2, 16), second_half=range(16, 31)):
    wildcard = variables["wildcard"]

    if 1 in wildcard:
        prob += wildcard[1] == 0

    prob += pulp.lpSum(wildcard[w] for w in first_half if w in wildcard) <= 1
    prob += pulp.lpSum(wildcard[w] for w in second_half if w in wildcard) <= 1


def add_uteam_usage_limit(prob, gws, variables, max_uses: int = 1):
    uteam = variables["uteam"]

    if 1 in uteam:
        prob += uteam[1] == 0

    prob += pulp.lpSum(uteam[w] for w in gws) <= max_uses


def add_fielded_permanent_link(prob, keys, variables):
    fielded = variables["fielded"]
    permanent = variables["permanent"]
    uteam = variables["uteam"]

    for k in keys:
        p, w = k
        prob += fielded[k] - permanent[k] <= uteam[w]
        prob += permanent[k] - fielded[k] <= uteam[w]


def add_permanent_freeze_on_uteam(prob, keys, variables):
    permanent = variables["permanent"]
    uteam = variables["uteam"]

    for p, player_gws_sorted in _gws_by_player(keys).items():
        for i, w in enumerate(player_gws_sorted):
            if i == 0:
                continue
            w_prev = player_gws_sorted[i - 1]
            k, k_prev = (p, w), (p, w_prev)
            prob += permanent[k] - permanent[k_prev] <= 1 - uteam[w]
            prob += permanent[k_prev] - permanent[k] <= 1 - uteam[w]


def add_uteam_credit(prob, keys, variables, lookups):
    """uteam_credit = what a held player puts towards the Loan rangers budget:
    his full price if he is kept in the fielded squad (cancelling his cost), his sale value if he is
    swapped out, and 0 if he is not held. Only upper bounds: more budget is never worse."""
    sale_proceeds = variables["sale_proceeds"]
    uteam_credit = variables["uteam_credit"]
    permanent = variables["permanent"]
    fielded = variables["fielded"]
    price = lookups["price_tenths"]

    for k in keys:
        prob += uteam_credit[k] <= price[k] * permanent[k]
        prob += uteam_credit[k] <= sale_proceeds[k] + price[k] * fielded[k]


def add_uteam_budget(prob, keys, variables, lookups, gws):
    """The fielded squad must be affordable from the bank plus the credit of the held players.
    Outside Loan rangers weeks fielded == permanent, so every player is kept and this holds automatically."""
    fielded = variables["fielded"]
    uteam_credit = variables["uteam_credit"]
    bank = variables["bank"]
    price = lookups["price_tenths"]

    keys_by_gw = _keys_by_gw(keys)
    for w in sorted(gws):
        keys_w = keys_by_gw[w]
        fielded_cost = pulp.lpSum(price[k] * fielded[k] for k in keys_w)
        prob += fielded_cost <= bank[w] + pulp.lpSum(uteam_credit[k] for k in keys_w)


def add_gameweek_pruning(prob, variables, pruned_keys: set[tuple[int, int]]):
    """pruned_keys: set of (player_id, gw) pairs to forcibly exclude from selection that week only."""
    permanent = variables["permanent"]
    fielded = variables["fielded"]

    for k in pruned_keys:
        if k in permanent:
            prob += permanent[k] == 0
        if k in fielded:
            prob += fielded[k] == 0