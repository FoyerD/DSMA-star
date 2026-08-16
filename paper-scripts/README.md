# Paper scripts

Scripts that regenerate every table and figure in the MP-BFS paper from the
raw benchmark results. Together with the tracked `imp_resutls/` results and
the algorithm source in this repo, they make the paper's numbers fully
reproducible (as claimed in the paper's reproducibility statement).

## What each script does

| Script | Emits | Backs |
|--------|-------|-------|
| `make_tables.py` | `tab_summary.tex`, `tab_perdepth.tex`, `tab_korf.tex`, `tab_amit.tex`, `facts.tex` | Tables 3, 4, 5, 2 and prose numbers |
| `make_figures.py` | `runtime_vs_depth`, `nodes_vs_depth`, `peak_memory_vs_depth`, `runtime_vs_optimality_gap` (each `.png` + `.pdf`) | Figures 1–4 |

## Data source

Both scripts read the raw, lossless `benchmark_results.csv` files:

- `imp_resutls/results_amit/benchmark_results.csv` — the amit suite
  (true optimal depths 21–40), the default for `--amit`
- `imp_resutls/results_korf/benchmark_results.csv` — the Korf 100 sample
  (depths 41/47/55), the default for `--korf`

Both files are tracked in git, so the scripts are deterministic and
reproduce the paper's numbers exactly.

## Usage

```bash
conda activate sai            # matplotlib (make_figures only)
python -u paper-scripts/make_tables.py --out ignore/Tables
python -u paper-scripts/make_figures.py --out ignore/Figures
```

The paper's LaTeX lives in the gitignored `ignore/` directory and references
`Tables/*.tex` and `Figures/*.png` relative to itself, so the `--out` paths
above are what the paper build expects. Override `--out`, `--amit`, or
`--korf` to point elsewhere (e.g. a fresh benchmark run).

`make_tables.py` without `--out` prints each block to stdout (useful for
diffing). `make_figures.py` requires `matplotlib` (already in
`requirements.txt`).

## Dependencies

- `make_tables.py` — Python stdlib only
- `make_figures.py` — Python stdlib + `matplotlib`

## Determinism

No RNG is used in either script; identical inputs always produce identical
outputs. The slight x-axis jitter in the trade-off figure
(`runtime_vs_optimality_gap`) is a fixed offset, not random.

## Building the paper

The LaTeX project itself is intentionally not tracked (it lives in the
gitignored `ignore/` dir). To compile the PDF after regenerating tables and
figures, run `paper-scripts/build_paper.sh` from the repo root.
