import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

SOLUTION_COLOR = "#2a78d6"
BOUND_COLOR = "#eb6834"
GAP_COLOR = "#52514e"
MUTED = "#8a8985"

# time-axis ticks at round human durations (seconds); the coarse set is used when the axis spans a long range
TIME_TICKS = [1, 2, 5, 10, 20, 30, 60, 2 * 60, 5 * 60, 10 * 60, 20 * 60, 30 * 60,
              3600, 2 * 3600, 5 * 3600, 10 * 3600, 20 * 3600, 48 * 3600, 96 * 3600]
COARSE_TIME_TICKS = [1, 5, 30, 2 * 60, 10 * 60, 3600, 5 * 3600, 24 * 3600, 96 * 3600]


def _format_seconds(s, _pos=None) -> str:
    if s < 60:
        return f"{s:g} s"
    if s < 3600:
        return f"{s / 60:g} min"
    return f"{s / 3600:g} h"


def _style_axes(ax) -> None:
    ax.grid(True, which="major", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors="#52514e")


def _log_time_axis(ax, label: str = "Solve time") -> None:
    """Call after plotting, so the data range is known."""
    ax.set_xscale("log")
    lo, hi = ax.get_xlim()
    ticks = COARSE_TIME_TICKS if hi / max(lo, 1e-9) > 300 else TIME_TICKS
    ax.xaxis.set_major_locator(mticker.FixedLocator(ticks))
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_seconds))
    ax.set_xlabel(label)


def relative_gap(convergence: pd.DataFrame) -> pd.Series:
    """Gurobi's MIP gap, |bound - obj| / |obj|. NaN until there is a positive incumbent."""
    obj = convergence["best_obj"].where(convergence["best_obj"] > 0)
    return (convergence["best_bound"] - obj).abs() / obj


def plot_convergence(convergence: pd.DataFrame, zoom_gap: float = 1.0):
    """Two panels on a shared log time axis: best solution and bound (top), relative gap (bottom).

    Both axes are zoomed to start at the first moment the gap drops below zoom_gap (1.0 = 100%);
    earlier values run off the panels but are not dropped. A gap of 0 (proven optimal) is drawn
    as a drop to the bottom edge of the gap panel, since a log scale cannot show 0.
    """
    df = convergence.dropna(subset=["best_bound"])
    t = df["time"]
    gap = relative_gap(df)

    fig, (ax_obj, ax_gap) = plt.subplots(2, 1, sharex=True, figsize=(8, 6), height_ratios=[3, 2])

    ax_obj.step(t, df["best_bound"], where="post", color=BOUND_COLOR, lw=2, label="Upper bound")
    ax_obj.step(t, df["best_obj"], where="post", color=SOLUTION_COLOR, lw=2, label="Best solution")

    within = df[gap <= zoom_gap]
    if len(within):
        lo, hi = within["best_obj"].iloc[0], within["best_bound"].iloc[0]
        pad = 0.05 * (hi - lo)
        ax_obj.set_ylim(lo - pad, hi + pad)
        ax_gap.set_xlim(within["time"].iloc[0] / 1.15, t.max() * 1.15)
    ax_obj.set_ylabel("Points")
    ax_obj.legend(frameon=False, loc="lower right")

    # log scale: draw a gap of 0 at a floor value at the bottom edge of the panel
    positive_gaps = gap[gap > 0]
    floor = positive_gaps.min() / 4
    gap_drawn = gap.where(gap > 0, floor).where(gap.notna())
    ax_gap.step(t, 100 * gap_drawn, where="post", color=GAP_COLOR, lw=2)
    top = gap[gap <= zoom_gap].max() if len(within) else positive_gaps.max()
    ax_gap.set_ylim(100 * floor, 100 * top * 1.5)

    ax_gap.set_yscale("log")
    ax_gap.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    ax_gap.set_ylabel("Relative gap")

    _log_time_axis(ax_gap)
    for ax in (ax_obj, ax_gap):
        _style_axes(ax)

    fig.tight_layout()
    return fig


def plot_pruning_tradeoff(results: pd.DataFrame, reference: tuple[float, float] | None = None,
                          reference_label: str = "no pruning"):
    """Score against solve time, one labelled point per pruning threshold.

    results: columns threshold, score, time_s. reference: (time_s, score) of the unpruned run, drawn
    as a separate point with a dashed line at its score.
    """
    df = results.sort_values("threshold")
    fig, ax = plt.subplots(figsize=(8, 4.5))

    ax.plot(df["time_s"], df["score"], color=SOLUTION_COLOR, lw=2, marker="o", markersize=8,
            markeredgecolor="white", markeredgewidth=2, zorder=3)
    for _, row in df.iterrows():
        ax.annotate(f"{row['threshold']:g}", (row["time_s"], row["score"]), xytext=(0, -16),
                    textcoords="offset points", ha="center", va="top", color="#52514e", fontsize=9)

    if reference is not None:
        ref_time, ref_score = reference
        ax.axhline(ref_score, color=MUTED, lw=1, ls="--", zorder=1)
        ax.plot([ref_time], [ref_score], color=GAP_COLOR, marker="o", markersize=8,
                markeredgecolor="white", markeredgewidth=2, ls="none", zorder=3)
        ax.annotate(f"{reference_label} ({ref_score:g})", (ref_time, ref_score), xytext=(-10, -6),
                    textcoords="offset points", ha="right", va="top", color="#52514e", fontsize=9)

    ax.margins(x=0.08, y=0.12)  # room for the point labels
    ax.set_ylabel("Points")
    _log_time_axis(ax)
    _style_axes(ax)
    fig.tight_layout()
    return fig
