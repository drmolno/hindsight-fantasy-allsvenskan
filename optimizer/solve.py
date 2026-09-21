import pulp
import pandas as pd

from optimizer.variables import build_keys, build_lookups, build_selection_variables, build_budget_variables, build_transfer_variables, build_captain_variables, build_chip_variables, build_dynamic_duo_linearization_variables, build_pdbus_variables, build_pdbus_linearization_variables, build_pdbus_captain_suppression_variables, build_wildcard_variables, build_uteam_variables, build_uteam_budget_variables
from optimizer.constraints import add_squad_start_link, add_squad_composition, add_formation, add_team_limit, add_buy_sell_link, add_bought_price_tracking, add_bank_balance, add_sale_proceeds, add_sale_proceeds_linearization, add_transfer_penalty, add_captain_constraints, add_dynamic_duo_linearization, add_chip_usage_limit, add_pdbus_linearization, add_pdbus_captain_suppression, add_chip_exclusivity, add_wildcard_window_limits, add_fielded_permanent_link, add_permanent_freeze_on_uteam, add_uteam_usage_limit, add_sale_value_if_held_linearization, add_uteam_budget
from optimizer.objective import set_season_objective

def extract_chips(gws, variables, chip_names: list[str]) -> pd.DataFrame:
    chip_rows = []
    for name in chip_names:
        chip_var = variables[name]
        chip_rows.extend({"gw": w, "chip": name} for w in gws if pulp.value(chip_var[w]) == 1)
    return pd.DataFrame(chip_rows) if chip_rows else pd.DataFrame(columns=["gw", "chip"])


def solve_all_gameweeks(stats: pd.DataFrame) -> pd.DataFrame:
    prob = pulp.LpProblem("optimal_season", pulp.LpMaximize)

    keys = build_keys(stats)
    lookups = build_lookups(stats)
    gws = stats["gw"].unique()

    variables = build_selection_variables(keys)
    variables.update(build_budget_variables(keys, gws, lookups))
    variables.update(build_transfer_variables(gws))  # merge into one dict
    variables.update(build_captain_variables(keys))
    variables.update(build_chip_variables(gws))
    variables.update(build_dynamic_duo_linearization_variables(keys))
    variables.update(build_pdbus_variables(gws))
    variables.update(build_pdbus_linearization_variables(keys))
    variables.update(build_pdbus_captain_suppression_variables(keys))
    variables.update(build_wildcard_variables(gws))
    variables.update(build_uteam_variables(gws))
    variables.update(build_uteam_budget_variables(keys, lookups))
    
    set_season_objective(prob, keys, variables, lookups, gws)

    add_sale_value_if_held_linearization(prob, keys, variables, lookups)
    add_uteam_budget(prob, keys, variables, lookups, gws)
    add_uteam_usage_limit(prob, gws, variables)
    add_fielded_permanent_link(prob, keys, variables)
    add_permanent_freeze_on_uteam(prob, keys, variables)
    add_pdbus_linearization(prob, keys, variables)
    add_pdbus_captain_suppression(prob, keys, variables)
    add_chip_usage_limit(prob, gws, variables, "2capt", max_uses=1)
    add_chip_usage_limit(prob, gws, variables, "pdbus", max_uses=1)
    add_chip_usage_limit(prob, gws, variables, "uteam", max_uses=1)
    add_dynamic_duo_linearization(prob, keys, variables)
    add_captain_constraints(prob, keys, variables, gws)
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

    add_chip_exclusivity(prob, gws, variables, ["2capt", "pdbus","wildcard","uteam"])
    add_wildcard_window_limits(prob, variables, gws)

    #prob.solve(pulp.PULP_CBC_CMD(msg=True, timeLimit = 30))
    prob.solve(pulp.PULP_CBC_CMD(msg=True))
    print(pulp.LpStatus[prob.status])

    fielded, start = variables["fielded"], variables["start"]
    rows = []
    for k in keys:
        if pulp.value(fielded[k]) == 1:
            p, w = k
            rows.append({
                "player_id": p,
                "gw": w,
                "in_squad": True,
                "in_starting_11": pulp.value(start[k]) == 1,
                "captain": pulp.value(variables["captain"][k]) == 1,
                "vice_captain": pulp.value(variables["vice"][k]) == 1,
            })
    picks = pd.DataFrame(rows)

    chips = extract_chips(gws, variables, ["2capt", "pdbus","wildcard","uteam"])

    return picks, chips
   