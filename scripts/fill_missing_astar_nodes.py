"""Fill missing total_nodes_a values using log-log regression on the
measured instances, and add a total_nodes_a_predicted flag column.

Usage:
    python scripts/fill_missing_astar_nodes.py
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("korfs100.csv")
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        sys.exit(1)

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Collect measured (ida, a) pairs for regression.
    measured = []
    for r in rows:
        ida = r.get("total_nodes_ida", "").strip()
        a = r.get("total_nodes_a", "").strip()
        if ida and a:
            measured.append((math.log(int(ida)), math.log(int(a))))

    n = len(measured)
    if n < 10:
        print(f"Only {n} measured instances — not enough for regression.")
        sys.exit(1)

    # Log-log linear regression.
    lx = [p[0] for p in measured]
    ly = [p[1] for p in measured]
    mean_lx = sum(lx) / n
    mean_ly = sum(ly) / n
    cov = sum((x - mean_lx) * (y - mean_ly) for x, y in zip(lx, ly))
    var = sum((x - mean_lx) ** 2 for x in lx)
    beta = cov / var
    alpha = mean_ly - beta * mean_lx

    # R^2
    ss_res = sum((y - (alpha + beta * x)) ** 2 for x, y in zip(lx, ly))
    ss_tot = sum((y - mean_ly) ** 2 for y in ly)
    r2 = 1 - ss_res / ss_tot

    print(f"Regression: a = {math.exp(alpha):.2f} * ida^{beta:.4f}  (R^2={r2:.4f})")
    print(f"Using {n} measured instances")

    # Add predicted column if missing.
    if "total_nodes_a_predicted" not in fieldnames:
        fieldnames.append("total_nodes_a_predicted")

    filled = 0
    for r in rows:
        ida = r.get("total_nodes_ida", "").strip()
        a = r.get("total_nodes_a", "").strip()
        if ida and not a:
            pred = int(math.exp(alpha + beta * math.log(int(ida))))
            r["total_nodes_a"] = str(pred)
            r["total_nodes_a_predicted"] = "True"
            filled += 1
        elif ida and a:
            r["total_nodes_a_predicted"] = "False"
        else:
            r["total_nodes_a_predicted"] = ""

    # Ensure a_approx is sqrt(ida) for all rows.
    for r in rows:
        ida = r.get("total_nodes_ida", "").strip()
        if ida and not r.get("total_nodes_a_approx", "").strip():
            r["total_nodes_a_approx"] = str(int(math.isqrt(int(ida))))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Filled {filled} instances with regression predictions.")
    print(f"Updated {csv_path}")


if __name__ == "__main__":
    main()
