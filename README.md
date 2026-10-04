# Hindsight Fantasy Allsvenskan

What is the highest score anyone could have reached in Fantasy Allsvenskan 2026, if they had known in advance how every player would perform?

This project answers that question by formulating the whole season as one integer program: squad selection, starting 11, captaincy, transfers, budget, and all four chips. It is solved with [Gurobi](https://www.gurobi.com/) through [PuLP](https://pypi.org/project/PuLP/). Solving it to proven optimality takes many hours, so the project also explores pruning strategies that trade a few points for much shorter solve times.

**Read the full write-up, with the formulation, results and open problems, on the [project website](https://drmolno.github.io/hindsight-fantasy-allsvenskan/).**

## Repository layout

| Folder | Contents |
|---|---|
| `optimizer/` | The integer program: variables, constraints, objective, pruning, and `solve_all_gameweeks` |
| `core/` | Everything around the optimizer: scoring, validation of a solution, budget replay, loading/saving, report tables and figures |
| `data/allsvenskan_data/` | Input data: `player_data.parquet` (one row per player and gameweek: position, club, price, points) and `names.parquet` |
| `solutions/` | Saved solutions (`picks_through_XX`, `chips_through_XX`), solver convergence logs, and experiment results |
| `reports/` | Source of the project website |
| `experiments/` | Notebooks for individual experiments |

## Getting started

Requires Python 3.10 or later and a Gurobi licence. Gurobi offers [free academic licences](https://www.gurobi.com/academia/academic-program-and-licenses/). Without one, `gurobipy` falls back to a size-limited licence that is far too small for this problem.

```bash
pip install -e .
pip install matplotlib   # for the figures
```

Put your licence file in your home folder (`~/gurobi.lic`) so that Gurobi finds it from any working directory.

## Running the optimizer

```python
from core.io import load_parquet, save_solution
from core.scoring import score_play
from core.validation import validate_play
from optimizer.solve import solve_all_gameweeks

stats = load_parquet("player_data.parquet")
stats = stats[stats["gw"] <= 10]   # optimize the first 10 gameweeks

picks, chips, convergence = solve_all_gameweeks(stats, time_limit=3600)

print(validate_play(picks, chips, stats))   # [] if the solution follows all rules
print(score_play(picks, chips, stats)["total"])
save_solution(picks, chips, through_gw=10, convergence=convergence)
```

Useful options of `solve_all_gameweeks`:

* `time_limit` (seconds) and `gap` (relative optimality gap, default 0.01%) control when the solver stops. Interrupting the solver also returns the best solution found so far.
* `pruned_keys` excludes `(player_id, gw)` pairs from the problem. Ready-made strategies are in [`optimizer/pruning.py`](optimizer/pruning.py), e.g. `prune_by_score_per_price(stats, threshold=0.4)` or `prune_by_clubs(stats, ["Hammarby", "AIK"])`.
* `chips` restricts which chips may be used, e.g. `chips=("wildcard",)` or `chips=()` for none.

Even 10 gameweeks can take hours to solve to optimality, and the full season much longer. Start small, or use pruning, to try things out.

## Try your own pruning strategy

The interesting open question is not the optimal score itself, but how to get close to it fast. A pruning strategy is any function that returns a set of `(player_id, gw)` pairs to leave out of the problem:

```python
def prune_my_way(stats):
    mask = (stats["points"] <= 0) & (stats["price"] > 8)   # e.g. expensive players who scored nothing
    return set(stats.loc[mask, ["player_id", "gw"]].itertuples(index=False, name=None))

picks, chips, convergence = solve_all_gameweeks(stats, pruned_keys=prune_my_way(stats))
```

Compare the score and solve time with the unpruned optimum. The more is pruned, the faster the solve, but prune a player the optimal solution needs and points are lost. Strategies that are provably safe, i.e. never prune anything an optimal solution would use, are listed as an open problem in the write-up.

## Checking a solution

A solution is two tables:

* **picks:** one row per player in the squad per gameweek, with columns `player_id`, `gw`, `in_starting_11`, `captain`, `vice_captain`
* **chips:** one row per chip played, with columns `gw` and `chip` (one of `2capt`, `pdbus`, `wildcard`, `uteam`, which are Dynamic duo, Park the bus, Wildcard and Loan rangers)

`validate_play(picks, chips, stats)` checks a solution against the rules (squad, formation, club limit, budget), and `score_play(picks, chips, stats)` scores it, independently of the optimizer. Our scoring reproduces the official score of a real team.

## Development notes

* Notebook outputs are stripped from commits by [nbstripout](https://github.com/kynan/nbstripout), so that plots do not bloat the repository. After cloning, run `pip install nbstripout` and `nbstripout --install`.
* All money in the optimizer is in tenths (a price of 5.5 is stored as 55), so that the budget constraints stay integer.
* The website is built with [Quarto](https://quarto.org/) from `reports/`, using the saved results in `solutions/`: `quarto render reports`.
