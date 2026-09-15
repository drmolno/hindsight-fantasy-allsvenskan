import pulp


def add_squad_start_link(prob, keys, variables):
    squad, start = variables["squad"], variables["start"]
    for k in keys:
        prob += start[k] <= squad[k] 


def add_squad_composition(prob, keys, variables, lookups, gws):
    squad = variables["squad"]
    pos = lookups["pos"]
    required = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}

    for w in gws:
        keys_w = [k for k in keys if k[1] == w]
        for p, req in required.items():
            prob += pulp.lpSum(squad[k] for k in keys_w if pos[k] == p) == req


def add_formation(prob, keys, variables, lookups, gws):
    start = variables["start"]
    pos = lookups["pos"]

    for w in gws:
        keys_w = [k for k in keys if k[1] == w]
        prob += pulp.lpSum(start[k] for k in keys_w) == 11
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "GK") == 1
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "DEF") >= 3
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "MID") >= 3
        prob += pulp.lpSum(start[k] for k in keys_w if pos[k] == "FWD") >= 1


def add_team_limit(prob, keys, variables, lookups, gws, max_per_team: int = 3):
    squad = variables["squad"]
    team = lookups["team"]

    for w in gws:
        keys_w = [k for k in keys if k[1] == w]
        teams_w = {team[k] for k in keys_w}
        for t in teams_w:
            prob += pulp.lpSum(squad[k] for k in keys_w if team[k] == t) <= max_per_team


def add_buy_sell_link(prob, keys, variables):
    squad = variables["squad"]
    buy = variables["buy"]
    sell = variables["sell"]

    keys_by_player = {}
    for k in keys:
        p, w = k
        keys_by_player.setdefault(p, []).append(w)

    for p, player_gws in keys_by_player.items():
        player_gws_sorted = sorted(player_gws)
        for i, w in enumerate(player_gws_sorted):
            k = (p, w)
            if i == 0:
                prob += buy[k] == squad[k]
                prob += sell[k] == 0
            else:
                w_prev = player_gws_sorted[i - 1]
                k_prev = (p, w_prev)
                prob += squad[k] - squad[k_prev] == buy[k] - sell[k]
                prob += buy[k] + sell[k] <= 1


def add_bought_price_tracking(prob, keys, variables, lookups):
    squad = variables["squad"]
    buy = variables["buy"]
    bought_price = variables["bought_price"]
    big_m = variables["big_m"]
    price = lookups["price_tenths"]

    keys_by_player = {}
    for k in keys:
        p, w = k
        keys_by_player.setdefault(p, []).append(w)

    for p, player_gws in keys_by_player.items():
        m = big_m[p]
        player_gws_sorted = sorted(player_gws)
        for i, w in enumerate(player_gws_sorted):
            k = (p, w)
            prob += bought_price[k] >= price[k] - m * (1 - buy[k])
            prob += bought_price[k] <= price[k] + m * (1 - buy[k])

            if i > 0:
                w_prev = player_gws_sorted[i - 1]
                k_prev = (p, w_prev)
                prob += bought_price[k] >= bought_price[k_prev] - m * (buy[k] + (1 - squad[k_prev]))
                prob += bought_price[k] <= bought_price[k_prev] + m * (buy[k] + (1 - squad[k_prev]))

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

    keys_set = set(keys)
    gws_sorted = sorted(gws)

    for i, w in enumerate(gws_sorted):
        keys_w = [k for k in keys_set if k[1] == w] 
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


def add_transfer_penalty(prob, keys, variables, gws, initial_free_transfers: int = 1, max_banked: int = 5):
    buy = variables["buy"]
    banked = variables["banked"]
    extra = variables["extra"]
    leftover = variables["leftover"]
    y = variables["over_zero"]

    gws_sorted = sorted(gws)
    keys_set = set(keys)

    for i, w in enumerate(gws_sorted):
        transfers_used = pulp.lpSum(buy[k] for k in keys_set if k[1] == w)

        if i == 0:
            prob += banked[w] == initial_free_transfers
            prob += extra[w] == 0
            prob += leftover[w] == 0
        else:
            prob += extra[w] >= transfers_used - banked[w]

            prob += leftover[w] <= (banked[w] - transfers_used) + max_banked * (1 - y[w])
            prob += leftover[w] >= (banked[w] - transfers_used) - max_banked * (1 - y[w])
            prob += leftover[w] <= max_banked * y[w]
            prob += leftover[w] >= -max_banked * y[w]

        if i + 1 < len(gws_sorted):
            w_next = gws_sorted[i + 1]
            prob += banked[w_next] == leftover[w] + 1