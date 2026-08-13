# Search Benchmark

A research framework for comparing **memory-bounded heuristic search
algorithms** on the **15-puzzle**. The original repo also built SMA* variants
(SMA*, Dynamic SMA*-Collapse, Two-Level Dynamic SMA*) and a Sokoban domain;
those were removed. The project now contains five clean, well-understood
algorithms:

- **A\*** (`algorithms/astar.py`) — classic graph-search A* with a binary
  heap. Optimal when `h` is admissible (Manhattan distance is). Keeps every
  generated node in RAM; fails on hard instances by exhausting memory.
- **ILBFS** (`algorithms/ilbfs.py`) — Iterative Linear Best-First Search:
  non-recursive RBFS (Collapse/Restore macros), O(b·d) memory.
- **RBFS** (`algorithms/rbfs.py`) — Recursive Best-First Search, O(b·d)
  memory via the recursion stack, ~3x faster than ILBFS.
- **mp-bfs** (`algorithms/mp_bfs.py`) — Multi-Path Best-First: many
  independent best-first "procs" (one per initial frontier path) multiplexed
  by a pluggable scheduler. Suboptimal solutions are possible.
- **mp-rbfs** (`algorithms/mp_rbfs.py`) — Multi-Path RBFS: the same proc
  architecture, but each proc runs a real iterative RBFS (Collapse/Restore)
  with a shared global tree. See `docs/mp_bfs.md` and `docs/mp_rbfs.md`.

> For the full project history, every issue found and solved, and the CLI
> reference, read **`AGENTS.md`**. It is the authoritative doc. The algorithm
> details live in `docs/ilbfs.md`, `docs/mp_bfs.md`, and `docs/mp_rbfs.md`.

## Quick start

```bash
conda activate sai
pip install -r requirements.txt        # psutil, pytest
python main.py --domain puzzle --seeds 0
python -m pytest tests/ -q
```

> `conda run` buffers stdout — use `python -u` and the direct python path
> (`/home/foyer/miniconda3/envs/sai/bin/python`) when you need live output.

## Instance sources — scramble depth is NOT optimal depth

- **`scramble`** — random walks from the goal. Scramble depth is *not* the
  true optimal solution length (moves cancel out).
- **`korf`** — `instances/korfs100.csv`: 100 fixed historical instances with
  true optimal depths and IDA*/A* node counts.
- **`amit`** — `instances/puzzle_amit_depths21_40.csv`: 20 instances at true
  optimal depths 21–40, A*-verified by `scripts/generate_depths21_40.py`.

```bash
# Korf instances by optimal depth
python main.py --domain puzzle --puzzle-instance-source korf --optimal-depths 40 45 50

# Amit instances (true depths 21-40)
python main.py --domain puzzle --puzzle-instance-source amit

# Multi-path variants (choose a scheduler: best_first, round_robin, etc.)
python main.py --domain puzzle --puzzle-instance-source amit --algorithms mp-rbfs-best_first
python main.py --domain puzzle --puzzle-instance-source amit --algorithms mp-bfs-best_first
```

## Submission benchmark

The full submission run needs more RAM than this repo's default machine, so
both runs are scripted in `run.sh` at the repo root (run on a bigger box with
`conda activate sai`):

```bash
bash run.sh    # amit 21-40 -> results_amit/  +  korf 41/47/55 -> results_korf/
```

Each `--output-dir` gets a raw, lossless `benchmark_results.csv/.json`, a
mean/std `benchmark_summary.csv/.json`, and an `analysis/` folder with curated
reports: `algorithm_summary.csv`, `by_difficulty_summary.csv`,
`proposed_algorithms_vs_baselines.csv`, `winners_by_instance.csv`,
`summary.json`, and `human_readable_summary.md`. On the hard end (amit d>=29,
korf d55) A* hits the memory ceiling and RBFS-family algorithms the node limit
— that is the expected data point, not a bug.

## Design notes

- **No wall-clock timeout.** A stopwatch favors A* (no memory-management
  overhead). Runs stop only on: solution found, RSS > memory ceiling, or the
  `--max-nodes` safety valve.
- **Memory ceiling via `psutil`** sampled every 256 limit-checks
  (`algorithms/_run_utils.py`), reported peak is
  `max(tracemalloc_peak, sampled_rss)`.

## Tests

```bash
python -m pytest tests/ -q
```

109 tests, all passing.
