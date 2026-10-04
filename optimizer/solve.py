import math

import pulp
import pandas as pd
from gurobipy import GRB

from optimizer.variables import build_keys, build_lookups, build_selection_variables, build_budget_variables, build_transfer_variables, build_chip_variables
from optimizer.constraints import add_squad_start_link, add_squad_composition, add_formation, add_team_limit, add_buy_sell_link, add_bought_price_tracking, add_bank_balance, add_sale_proceeds, add_sale_proceeds_linearization, add_transfer_penalty, add_captain_constraints, add_dynamic_duo_linearization, add_chip_usage_limit, add_pdbus_linearization, add_pdbus_captain_suppression, add_chip_exclusivity, add_wildcard_window_limits, add_fielded_permanent_link, add_permanent_freeze_on_uteam, add_uteam_usage_limit, add_uteam_credit, add_uteam_budget, add_gameweek_pruning
from optimizer.objective import set_season_objective

ALL_CHIPS = ("2capt", "pdbus", "wildcard", "uteam")

def extract_chips(gws, variables, chip_names: list[str]) -> pd.DataFrame:
    chip_rows = []
    for name in chip_names:
        chip_var = variables[name]
        chip_rows.extend({"gw": w, "chip": name} for w in gws if pulp.value(chip_var[w]) > 0.5)
    return pd.DataFrame(chip_rows) if chip_rows else pd.DataFrame(columns=["gw", "chip"])


def _finite(x: float) -> float:
    # Gurobi reports +-1e100 when there is no incumbent / bound yet
    return math.nan if abs(x) >= GRB.INFINITY else x


def make_convergence_tracker():
    """Gurobi callback that logs a row every time the incumbent or the bound improves."""
    rows = []
    last = {"obj": None, "bound": None}

    def changed(new, old):
        return not (new == old or (old is not None and math.isnan(new) and math.isnan(old)))

    def record(time, obj, bound):
        obj, bound = _finite(obj), _finite(bound)
        new_obj, new_bound = changed(obj, last["obj"]), changed(bound, last["bound"])
        if not (new_obj or new_bound):
            return
        rows.append({"time": time, "best_obj": obj, "best_bound": bound,
                     "new_obj": new_obj, "new_bound": new_bound})
        last["obj"], last["bound"] = obj, bound

    def callback(model, where):
        if where == GRB.Callback.MIP:
            record(model.cbGet(GRB.Callback.RUNTIME),
                   model.cbGet(GRB.Callback.MIP_OBJBST),
                   model.cbGet(GRB.Callback.MIP_OBJBND))
        elif where == GRB.Callback.MIPSOL:
            record(model.cbGet(GRB.Callback.RUNTIME),
                   model.cbGet(GRB.Callback.MIPSOL_OBJBST),
                   model.cbGet(GRB.Callback.MIPSOL_OBJBND))

    return callback, record, rows


def solve_all_gameweeks(stats: pd.DataFrame, pruned_keys: set[tuple[int, int]] | None = None, gap: float = 1e-4, time_limit: float | None = None, chips: tuple[str, ...] = ALL_CHIPS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """chips: the chips the optimizer may use (any of ALL_CHIPS); the others are forbidden."""
    if pruned_keys is None:
        pruned_keys = set()
    unknown = set(chips) - set(ALL_CHIPS)
    if unknown:
        raise ValueError(f"Unknown chip(s): {sorted(unknown)}. Valid chips: {list(ALL_CHIPS)}")

    prob = pulp.LpProblem("optimal_season", pulp.LpMaximize)

    keys = build_keys(stats)
    lookups = build_lookups(stats)
    gws = stats["gw"].unique()

    variables = build_selection_variables(keys)
    variables.update(build_budget_variables(keys, gws, lookups))
    variables.update(build_transfer_variables(gws))
    variables.update(build_chip_variables(keys, gws))

    set_season_objective(prob, keys, variables, lookups, gws)

    add_uteam_credit(prob, keys, variables, lookups)
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

    add_chip_exclusivity(prob, gws, variables, list(ALL_CHIPS))
    add_wildcard_window_limits(prob, variables)

    # chips not allowed in this run are forbidden; presolve then removes their variables
    for chip in ALL_CHIPS:
        if chip not in chips:
            add_chip_usage_limit(prob, gws, variables, chip, max_uses=0)

    add_gameweek_pruning(prob, variables, pruned_keys)

    callback, record, convergence_rows = make_convergence_tracker()
    prob.solve(pulp.GUROBI(msg=True, gapRel=gap, timeLimit=time_limit), callback=callback)

    # The final bound tightening (e.g. proving optimality) may not trigger a callback
    model = prob.solverModel
    if model.SolCount > 0:
        record(model.Runtime, model.ObjVal, model.ObjBound)
    convergence = pd.DataFrame(convergence_rows, columns=["time", "best_obj", "best_bound", "new_obj", "new_bound"])

    print(pulp.LpStatus[prob.status])

    fielded, start = variables["fielded"], variables["start"]
    rows = []
    for k in keys:
        if pulp.value(fielded[k]) > 0.5:
            p, w = k
            rows.append({
                "player_id": p,
                "gw": w,
                "in_squad": True,
                "in_starting_11": pulp.value(start[k]) > 0.5,
                "captain": pulp.value(variables["captain"][k]) > 0.5,
                "vice_captain": pulp.value(variables["vice"][k]) > 0.5,
            })
    picks = pd.DataFrame(rows)

    chips_used = extract_chips(gws, variables, list(ALL_CHIPS))

    return picks, chips_used, convergence
   