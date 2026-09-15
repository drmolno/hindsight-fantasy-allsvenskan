import pulp


def set_points_and_transfer_objective(prob, keys, variables, lookups, gws):
    start = variables["start"]
    points = lookups["points"]
    extra = variables["extra"]

    total_points = pulp.lpSum(points[k] * start[k] for k in keys)
    total_penalty = 4*pulp.lpSum(extra[w] for w in gws)
    prob.setObjective(total_points-total_penalty)