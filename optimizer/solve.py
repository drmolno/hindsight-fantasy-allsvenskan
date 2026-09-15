import pulp
import pandas as pd

from optimizer.variables import build_keys, build_lookups, build_selection_variables, build_budget_variables, build_transfer_variables
from optimizer.constraints import add_squad_start_link, add_squad_composition, add_formation, add_team_limit, add_buy_sell_link, add_bought_price_tracking, add_bank_balance, add_sale_proceeds, add_sale_proceeds_linearization, add_transfer_penalty
from optimizer.objective import set_points_and_transfer_objective


def solve_all_gameweeks(stats: pd.DataFrame) -> pd.DataFrame:
    prob = pulp.LpProblem("optimal_season", pulp.LpMaximize)

    keys = build_keys(stats)
    lookups = build_lookups(stats)
    gws = stats["gw"].unique()

    variables = build_selection_variables(keys)
    variables.update(build_budget_variables(keys, gws, lookups))
    variables.update(build_transfer_variables(gws))  # merge into one dict

    set_points_and_transfer_objective(prob, keys, variables, lookups, gws)

    add_squad_start_link(prob, keys, variables)
    add_squad_composition(prob, keys, variables, lookups, gws)
    add_formation(prob, keys, variables, lookups, gws)
    add_team_limit(prob, keys, variables, lookups, gws)

    add_buy_sell_link(prob, keys, variables)
    add_bought_price_tracking(prob, keys, variables, lookups)
    add_sale_proceeds(prob, keys, variables, lookups)
    add_sale_proceeds_linearization(prob, keys, variables, lookups)
    add_bank_balance(prob, keys, variables, lookups, gws, initial_budget=100.0)

    add_transfer_penalty(prob, keys, variables, gws)

    #prob.solve(pulp.PULP_CBC_CMD(msg=True, timeLimit = 30))
    prob.solve(pulp.PULP_CBC_CMD(msg=True))
    print(pulp.LpStatus[prob.status])

    squad, start = variables["squad"], variables["start"]
    rows = []
    for k in keys:
        if pulp.value(squad[k]) == 1:
            p, w = k
            rows.append({
                "player_id": p,
                "gw": w,
                "in_squad": True,
                "in_starting_11": pulp.value(start[k]) == 1,
                "captain": False,
                "vice_captain": False,
            })

    #bank = variables["bank"]
    #for gw in gws:
    #    print(f"Bank gw {gw}: {pulp.value(bank[gw])}")
    #print()

    #for w in sorted(gws):
    #    pts = sum(lookups["points"][k] * pulp.value(variables["start"][k]) for k in keys if k[1] == w)
    #    pen = 4 * pulp.value(variables["extra"][w])
    #    print(w, pts, pen)

    #for w in sorted(gws):
    #    transfers = sum(pulp.value(variables["buy"][k]) for k in keys if k[1] == w)
    #    bank_val = pulp.value(variables["banked"][w])
    #    extra_val = pulp.value(variables["extra"][w])
    #    print(f"gw{w}: transfers={transfers}, banked={bank_val}, extra={extra_val}, penalty={4*extra_val}")

    return pd.DataFrame(rows)