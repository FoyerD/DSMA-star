#!/usr/bin/env python
"""Generate the figures for the MP-BFS paper from the raw benchmark CSVs.

This is a paper deliverable: together with the tracked raw results under
`imp_resutls/`, it regenerates every figure in the paper. Figures are written
as PNG (and PDF) into `Figures/` under the given output dir; the paper build
uses the default `--out ignore/Figures` so the tex's relative
`Figures/<name>.png` paths line up.

Emitted figures and the paper figures they back:
    runtime_vs_depth          -> Figure 1
    nodes_vs_depth            -> Figure 2
    peak_memory_vs_depth      -> Figure 3
    runtime_vs_optimality_gap -> Figure 4

Usage:
    python paper-scripts/make_figures.py [--amit DIR] [--korf DIR] [--out DIR]

Requires matplotlib (see requirements.txt). Deterministic: no RNG is used.
"""

import argparse
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lines drawn in the per-depth figures, in the paper's canonical order.
FIG_ALGOS = [
    ("astar", "A*"),
    ("rbfs", "RBFS"),
    ("ilbfs", "ILBFS"),
    ("mp-bfs-best_first", "MP-BFS (BF)"),
    ("mp-bfs-round_robin", "MP-BFS (RR)"),
    ("mp-bfs-proportional", "MP-BFS (Prop)"),
    ("mp-rbfs-best_first", "MP-RBFS (BF)"),
]

# The trade-off figure additionally shows the suboptimal MP-RBFS schedulers,
# which only have data on the (runtime, optimality-gap) axes they exercise.
TRADEOFF_ALGOS = FIG_ALGOS + [
    ("mp-rbfs-round_robin", "MP-RBFS (RR)"),
    ("mp-rbfs-proportional", "MP-RBFS (Prop)"),
]

MARKERS = {
    "astar": "o",
    "rbfs": "s",
    "ilbfs": "^",
    "mp-bfs-best_first": "D",
    "mp-bfs-round_robin": "v",
    "mp-bfs-proportional": "P",
    "mp-rbfs-best_first": "X",
    "mp-rbfs-round_robin": "*",
    "mp-rbfs-proportional": "+",
}

AMIT_DEPTHS = list(range(21, 41))


def load_results(csv_path):
    out = {}
    if not os.path.exists(csv_path):
        return out
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["algorithm_name"], {})[row["instance_id"]] = row
    return out


def amit_by_depth(results):
    """Return {algo: {depth: row}} for the amit dataset."""
    out = {}
    for algo, rows in results.items():
        for iid, row in rows.items():
            if iid.startswith("amit") and "_d" in iid:
                depth = int(iid.split("_d")[1])
                out.setdefault(algo, {})[depth] = row
    return out


def success(row):
    return (row.get("success") or "").strip().lower() == "true"


def per_depth_figure(amit, metric, name, ylabel, out_dir):
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    for algo, label in FIG_ALGOS:
        rows = amit.get(algo, {})
        if not rows:
            continue
        xs, ys = [], []
        for depth in AMIT_DEPTHS:
            row = rows.get(depth)
            if row is None:
                continue
            if not success(row):
                continue  # leave a gap in the curve
            try:
                xs.append(depth)
                ys.append(float(row[metric]))
            except (ValueError, KeyError):
                continue
        if not xs:
            continue
        ax.plot(xs, ys, marker=MARKERS.get(algo, "."), label=label, linewidth=1.5)
    ax.set_xlabel("Optimal solution depth")
    ax.set_ylabel(ylabel)
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"), dpi=300)
    plt.close(fig)
    print(f"wrote {name}.png/.pdf")


def tradeoff_figure(amit, out_dir):
    """Average runtime (solved) vs average optimality gap (amit)."""
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    for algo, label in TRADEOFF_ALGOS:
        rows = amit.get(algo, {})
        if not rows:
            continue
        rts, gaps = [], []
        for depth in AMIT_DEPTHS:
            row = rows.get(depth)
            if row is None or not success(row):
                continue
            rts.append(float(row["runtime_seconds"]))
            gaps.append(
                float(row["solution_cost"]) - float(row["known_optimal_depth"])
            )
        if not rts:
            continue
        # Slight horizontal jitter so algorithms with the same (zero) gap do
        # not sit exactly on top of one another on a linear x-axis.
        gx = sum(gaps) / len(gaps) + 0.015 * (len(ax.collections) - 2)
        ax.scatter(
            [gx], [sum(rts) / len(rts)],
            marker=MARKERS.get(algo, "."), s=70, label=label, zorder=3,
        )
    ax.set_xlabel("Average optimality gap (moves above optimal)")
    ax.set_ylabel("Average runtime on solved instances (s)")
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out_dir, f"runtime_vs_optimality_gap.{ext}"), dpi=300)
    plt.close(fig)
    print("wrote runtime_vs_optimality_gap.png/.pdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amit", default=os.path.join(REPO_ROOT, "imp_resutls", "results_amit"))
    ap.add_argument("--korf", default=os.path.join(REPO_ROOT, "imp_resutls", "results_korf"))
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "ignore", "Figures"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    amit_res = load_results(os.path.join(args.amit, "benchmark_results.csv"))
    amit = amit_by_depth(amit_res)

    per_depth_figure(amit, "runtime_seconds", "runtime_vs_depth",
                     "Runtime (s, log scale)", args.out)
    per_depth_figure(amit, "nodes_expanded", "nodes_vs_depth",
                     "Nodes expanded (log scale)", args.out)
    per_depth_figure(amit, "peak_memory_mb", "peak_memory_vs_depth",
                     "Peak memory (MB, log scale)", args.out)
    tradeoff_figure(amit, args.out)


if __name__ == "__main__":
    main()
