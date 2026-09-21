import pulp


#def set_points_transfer_captain_objective(prob, keys, variables, lookups, gws):
#    start = variables["start"]
#    captain = variables["captain"]
#    extra = variables["extra"]
#    points = lookups["points"]
#
#    base_points = pulp.lpSum(points[k] * start[k] for k in keys)
#    captain_bonus = pulp.lpSum(points[k] * captain[k] for k in keys)  # +1x extra when captained, giving 2x total
#    transfer_cost = 4 * pulp.lpSum(extra[w] for w in gws)
#
#    prob.setObjective(base_points + captain_bonus - transfer_cost)


def set_season_objective(prob, keys, variables, lookups, gws):
    start = variables["start"]
    captain = variables["captain"]
    cap_2c = variables["cap_2c"]
    vice_2c = variables["vice_2c"]
    start_pdbus = variables["start_pdbus"]
    cap_pdbus = variables["cap_pdbus"]
    extra = variables["extra"]
    points = lookups["points"]
    is_defender = {k: 1 if lookups["pos"][k] == "DEF" else 0 for k in keys}

    base_points = pulp.lpSum(points[k] * start[k] for k in keys)
    captain_bonus = pulp.lpSum(points[k] * captain[k] for k in keys)
    two_capt_extra = pulp.lpSum(points[k] * cap_2c[k] for k in keys)
    two_capt_vice_bonus = pulp.lpSum(points[k] * vice_2c[k] for k in keys)
    pdbus_defender_bonus = pulp.lpSum(points[k] * is_defender[k] * start_pdbus[k] for k in keys)
    pdbus_captain_removal = pulp.lpSum(points[k] * cap_pdbus[k] for k in keys)  # subtract this back out
    total_penalty = 4 * pulp.lpSum(extra[w] for w in gws)

    prob.setObjective(
        base_points
        + captain_bonus 
        + two_capt_extra 
        + two_capt_vice_bonus
        + pdbus_defender_bonus
        - pdbus_captain_removal
        - total_penalty
    )