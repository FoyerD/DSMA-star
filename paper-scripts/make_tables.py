#!/usr/bin/env python
"""Generate the LaTeX tables for the MP-BFS paper from the raw benchmark CSVs.

This is a paper deliverable: together with the tracked raw results under
`imp_resutls/`, it regenerates every table in the paper. The paper's numbers
are always pulled from the raw, lossless `benchmark_results.csv` files (one
per output dir) so that re-running this script after a new benchmark run
refreshes every table without hand-editing the tex.

Emitted blocks and the paper tables they back:
    tab_summary   -> Table 3  (aggregate results, amit dataset)
    tab_perdepth  -> Table 4  (per-depth runtime / nodes / cost, amit)
    tab_korf      -> Table 5  (Korf 100 sample)
    tab_amit      -> Table 2  (amit instance dataset description)
    facts         -> prose numbers quoted in the text

Usage:
    python paper-scripts/make_tables.py [--amit DIR] [--korf DIR] [--out DIR]

Default DIRs are the archived runs under `imp_resutls/`. Each table is written
to its own .tex file under `--out` (default: stdout-ish print); the paper
build uses `--out ignore/Tables`. Rows for algorithms that are not present in
a given CSV are emitted as ``N/A`` so the table is stable while a run is
still in flight.

Only stdlib is required.
"""

import argparse
import csv
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Canonical order + display names used in the paper.
ALGO_ORDER = [
    "astar",
    "rbfs",
    "ilbfs",
    "mp-bfs-best_first",
    "mp-bfs-round_robin",
    "mp-bfs-proportional",
    "mp-rbfs-best_first",
    "mp-rbfs-round_robin",
    "mp-rbfs-proportional",
]

ALGO_NAMES = {
    "astar": "A*",
    "rbfs": "RBFS",
    "ilbfs": "ILBFS",
    "mp-bfs-best_first": "MP-BFS (Best-First)",
    "mp-bfs-round_robin": "MP-BFS (Round-Robin)",
    "mp-bfs-proportional": "MP-BFS (Proportional)",
    "mp-rbfs-best_first": "MP-RBFS (Best-First)",
    "mp-rbfs-round_robin": "MP-RBFS (Round-Robin)",
    "mp-rbfs-proportional": "MP-RBFS (Proportional)",
}

# Short labels for narrow tables.
ALGO_SHORT = {
    "astar": "A*",
    "rbfs": "RBFS",
    "ilbfs": "ILBFS",
    "mp-bfs-best_first": "MP-BFS (BF)",
    "mp-bfs-round_robin": "MP-BFS (RR)",
    "mp-bfs-proportional": "MP-BFS (Prop)",
    "mp-rbfs-best_first": "MP-RBFS (BF)",
    "mp-rbfs-round_robin": "MP-RBFS (RR)",
    "mp-rbfs-proportional": "MP-RBFS (Prop)",
}

# Depths shown in the representative per-depth table.
PERDEPTH_DEPTHS = [21, 24, 28, 30, 35, 38, 40]


def load_results(csv_path):
    """Return {algorithm_name: {depth_or_instance_id: row}}."""
    out = {}
    if not os.path.exists(csv_path):
        return out
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            out.setdefault(row["algorithm_name"], {})[
                row["instance_id"]
            ] = row
    return out


def row_success(row):
    return (row.get("success") or "").strip().lower() == "true"


def f_int(v, digits=0):
    """Format an int-ish value with LaTeX thousands separators."""
    if v == "" or v is None:
        return "N/A"
    f = float(v)
    if digits:
        s = f"{f:,.{digits}f}"
    else:
        s = f"{f:,.0f}"
    return s.replace(",", "{,}")


def f_sec(v, digits=2):
    if v == "" or v is None:
        return "N/A"
    return f"{float(v):.{digits}f}"


def f_mem(v, digits=1):
    if v == "" or v is None:
        return "N/A"
    return f"{float(v):.{digits}f}"


def f_gap(v, digits=1):
    if v == "" or v is None:
        return "N/A"
    return f"{float(v):.{digits}f}"


def amit_instances():
    """[(id, key, optimal_depth)] for the amit dataset, ordered by depth.

    `key` is the instance_id used in benchmark_results.csv (``amit{id}_d{depth}``).
    """
    csv_path = os.path.join(REPO_ROOT, "instances", "puzzle_amit_depths21_40.csv")
    insts = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            iid, depth = row["id"], int(row["optimal_depth"])
            insts.append((iid, f"amit{iid}_d{depth}", depth))
    insts.sort(key=lambda t: t[2])
    return insts


def korf_reference():
    """{korf_id: {'optimal_depth', 'total_nodes_a', 'predicted'}} from korfs100.csv."""
    csv_path = os.path.join(REPO_ROOT, "instances", "korfs100.csv")
    ref = {}
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ref[row["id"]] = {
                "optimal_depth": int(row["optimal_depth"]),
                "total_nodes_a": row["total_nodes_a"],
                "predicted": (row.get("total_nodes_a_predicted") or "").lower()
                == "true",
            }
    return ref


def korf_id_of(instance_id):
    """Extract the Korf id (``55``) from an instance_id like ``korf55_d41``."""
    prefix = instance_id.split("_d")[0]
    return prefix[len("korf"):] if prefix.startswith("korf") else prefix


def amit_aggregates(results, algorithms):
    """Per-algorithm aggregates over the 20-instance amit dataset.

    Returns {algo: dict(solved, avg_runtime_solved, avg_mem_all,
    avg_nodes_all, avg_gap_solved, fail_depths)}.
    """
    insts = amit_instances()
    agg = {}
    for algo in algorithms:
        rows = results.get(algo, {})
        if not rows:
            agg[algo] = {
                "present": False, "solved": None, "avg_runtime_solved": None,
                "avg_mem_all": None, "avg_nodes_all": None,
                "avg_gap_solved": None, "fail_depths": [],
            }
            continue
        solved_r = []
        mems, nodes = [], []
        gaps = []
        fails = []
        for _, key, depth in insts:
            row = rows.get(key)
            if row is None:
                continue
            mems.append(float(row["peak_memory_mb"]))
            nodes.append(float(row["nodes_expanded"]))
            if row_success(row):
                solved_r.append(float(row["runtime_seconds"]))
                gaps.append(
                    float(row["solution_cost"])
                    - float(row["known_optimal_depth"])
                )
            else:
                fails.append(depth)
        agg[algo] = {
            "present": True,
            "solved": len(solved_r),
            "avg_runtime_solved": (sum(solved_r) / len(solved_r)) if solved_r else None,
            "avg_mem_all": (sum(mems) / len(mems)) if mems else None,
            "avg_nodes_all": (sum(nodes) / len(nodes)) if nodes else None,
            "avg_gap_solved": (sum(gaps) / len(gaps)) if gaps else None,
            "fail_depths": sorted(fails),
        }
    return agg


def emit_summary(results):
    print("%% tab:summary -- amit aggregate (20 instances, depths 21--40)")
    print(r"\begin{tabular}{lccccc}")
    print(r"\toprule")
    print(
        r"Algorithm & Solved & Avg.\ runtime (s) & Avg.\ peak mem.\ (MB) "
        r"& Avg.\ nodes expanded & Avg.\ opt.\ gap (moves) \\"
    )
    print(r"\midrule")
    agg = amit_aggregates(results, ALGO_ORDER)
    for algo in ALGO_ORDER:
        a = agg[algo]
        if not a["present"]:
            cell = r"\textsc{N/A}"
            print(f"{ALGO_NAMES[algo]} & {cell} & {cell} & {cell} & {cell} & {cell} \\\\")
            continue
        solved = f"{a['solved']}/20" if a["solved"] is not None else "N/A"
        rt = f_sec(a["avg_runtime_solved"]) if a["avg_runtime_solved"] is not None else r"\textsc{fail}"
        mem = f_mem(a["avg_mem_all"])
        nd = f_int(a["avg_nodes_all"])
        gap = f_gap(a["avg_gap_solved"]) if a["avg_gap_solved"] is not None else r"\textsc{---}"
        print(f"{ALGO_NAMES[algo]} & {solved} & {rt} & {mem} & {nd} & {gap} \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print()


def emit_perdepth(results):
    print("%% tab:perdepth -- representative depths, amit dataset")
    insts = amit_instances()
    depth_to_key = {d: k for _, k, d in insts}
    cols = ["astar", "ilbfs", "rbfs", "mp-bfs-best_first",
            "mp-bfs-round_robin", "mp-bfs-proportional"]
    n = len(cols)
    groups = " & ".join(
        r"\multicolumn{3}{c}{%s}" % ALGO_SHORT[c] for c in cols
    )
    metrics = " & ".join([r"Runtime (s) & Nodes & Cost"] * n)
    cmid = " ".join(
        r"\cmidrule(lr){%d-%d}" % (2 + 3 * i, 4 + 3 * i) for i in range(n)
    )
    print(r"\resizebox{\textwidth}{!}{" + r"\setlength{\tabcolsep}{2pt}")
    print(r"\begin{tabular}{l*{%d}{rrr}}" % n)
    print(r"\toprule")
    print(r"Depth & " + groups + r" \\")
    print(cmid)
    print(r" & " + metrics + r" \\")
    print(r"\midrule")
    for depth in PERDEPTH_DEPTHS:
        cells = [str(depth)]
        key = depth_to_key[depth]
        for algo in cols:
            row = (results.get(algo) or {}).get(key)
            if row is None:
                cells.append(r"\multicolumn{3}{c}{\textsc{N/A}}")
                continue
            if not row_success(row):
                cells.append(r"\multicolumn{3}{c}{\textbf{fail}}")
                continue
            t = f_sec(row["runtime_seconds"])
            nd = f_int(row["nodes_expanded"])
            cost = float(row["solution_cost"])
            opt = float(row["known_optimal_depth"])
            cost_s = str(int(cost)) if cost == int(cost) else f_gap(cost)
            if cost > opt:
                cost_s = r"\textbf{" + cost_s + "}"
            cells.extend([t, nd, cost_s])
        print(" & ".join(cells) + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}}")
    print()


def emit_korf(results):
    print("%% tab:korf -- deeper Korf instances (optimal depths 41/47/55)")
    ref = korf_reference()
    cols = ["astar", "rbfs", "mp-bfs-best_first",
            "mp-bfs-round_robin", "mp-bfs-proportional", "mp-rbfs-best_first"]
    # Distinct korf instances present in the results, ordered by depth.
    seen = {}
    for rows in results.values():
        for iid in rows:
            kid = korf_id_of(iid)
            if kid in ref:
                seen.setdefault(iid, ref[kid]["optimal_depth"])
    instances = sorted(seen.items(), key=lambda kv: kv[1])
    if not instances:
        print("% no korf results found")
        return
    print(r"\begin{tabular}{p{2.7cm}" + "p{2.0cm}" * len(cols) + "}")
    print(r"\toprule")
    print(
        r"Instance (depth) & " + " & ".join(ALGO_SHORT[c] for c in cols) + r" \\"
    )
    print(r"\midrule")
    for iid, depth in instances:
        kid = korf_id_of(iid)
        kref = ref[kid]
        label = f"korf{kid} ({depth}"
        if kref["total_nodes_a"]:
            label += f"; A* ref.~{f_int(kref['total_nodes_a'])}"
        if kref["predicted"]:
            label += ", regression-predicted"
        label += ")"
        cells = [label]
        for algo in cols:
            row = (results.get(algo) or {}).get(iid)
            if row is None:
                cells.append(r"\textsc{N/A}")
                continue
            if not row_success(row):
                cells.append(r"\textbf{fail}")
                continue
            t = f_sec(row["runtime_seconds"])
            cost = float(row["solution_cost"])
            opt = float(row["known_optimal_depth"])
            cost_s = str(int(cost)) if cost == int(cost) else f_gap(cost)
            if cost > opt:
                cost_s = r"\textbf{" + cost_s + "}"
            cells.append(f"{t}s / {cost_s}")
        print(" & ".join(cells) + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print()


def emit_amit_dataset(results):
    print("%% tab:amit -- the amit dataset (constructed and A*-verified by us)")
    insts = amit_instances()
    astar_rows = results.get("astar", {})
    print(r"\begin{tabular}{lcc}")
    print(r"\toprule")
    print(r"Instance & Optimal depth & A* nodes expanded \\")
    print(r"\midrule")
    for iid, key, depth in insts:
        row = astar_rows.get(key)
        nd = f_int(row["nodes_expanded"]) if row and row_success(row) else r"\textsc{---}"
        print(f"amit{iid} & {depth} & {nd} \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print()


def emit_facts(amit_res, korf_res):
    print("%% Facts used in the prose (key: value)")
    agg = amit_aggregates(amit_res, ALGO_ORDER)
    facts = []
    for algo in ["astar", "rbfs", "ilbfs", "mp-bfs-best_first", "mp-rbfs-best_first"]:
        a = agg[algo]
        if a["present"]:
            facts.append(
                f"amit.{algo}: solved={a['solved']}/20 "
                f"avg_rt_solved={f_sec(a['avg_runtime_solved'])} "
                f"avg_mem_all={f_mem(a['avg_mem_all'])} "
                f"avg_nodes_all={f_int(a['avg_nodes_all'])} "
                f"avg_gap={f_gap(a['avg_gap_solved'])} "
                f"fail_depths={a['fail_depths']}"
            )
    for f_ in facts:
        print(f"% {f_}")

    korf_insts = sorted(
        set(
            iid.split("_d")[0]
            for rows in korf_res.values()
            for iid in rows
        )
    )
    print(f"% korf.instances={korf_insts}")
    for algo in ["astar", "rbfs", "mp-bfs-best_first", "mp-rbfs-best_first"]:
        rows = korf_res.get(algo, {})
        if not rows:
            continue
        solved = sum(1 for r in rows.values() if row_success(r))
        print(f"% korf.{algo}: solved={solved}/{len(rows)}")
        for iid, r in sorted(rows.items()):
            if row_success(r):
                print(
                    f"%   {iid}: rt={f_sec(r['runtime_seconds'])} "
                    f"exp={f_int(r['nodes_expanded'])} "
                    f"cost={float(r['solution_cost']):.0f} "
                    f"mem={f_mem(r['peak_memory_mb'])}"
                )
            else:
                lim = "node" if (r.get("node_limit_reached") or "").lower() == "true" else "mem"
                print(
                    f"%   {iid}: {lim}-limit "
                    f"exp={f_int(r['nodes_expanded'])} "
                    f"gen={f_int(r['nodes_generated'])}"
                )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amit", default=os.path.join(REPO_ROOT, "imp_resutls", "results_amit"))
    ap.add_argument("--korf", default=os.path.join(REPO_ROOT, "imp_resutls", "results_korf"))
    ap.add_argument("--out", default=None, help="optional directory for .tex outputs")
    args = ap.parse_args()

    amit_res = load_results(os.path.join(args.amit, "benchmark_results.csv"))
    korf_res = load_results(os.path.join(args.korf, "benchmark_results.csv"))

    blocks = [
        ("tab_summary", lambda: emit_summary(amit_res)),
        ("tab_perdepth", lambda: emit_perdepth(amit_res)),
        ("tab_korf", lambda: emit_korf(korf_res)),
        ("tab_amit", lambda: emit_amit_dataset(amit_res)),
        ("facts", lambda: emit_facts(amit_res, korf_res)),
    ]

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        for name, fn in blocks:
            with open(os.path.join(args.out, name + ".tex"), "w") as fh:
                import contextlib

                with contextlib.redirect_stdout(fh):
                    fn()
                fh.write("% do not hand-edit; regenerate with paper-scripts/make_tables.py\n")
    else:
        for name, fn in blocks:
            fn()


if __name__ == "__main__":
    main()
