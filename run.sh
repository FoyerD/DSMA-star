#!/usr/bin/env bash
# Submission benchmark runs. Execute on a machine with enough RAM (see the
# memory-ceiling note at the bottom). Run from the repo root, with the conda
# env `sai` active.
#
# Each run writes into its own --output-dir so the raw benchmark_results.csv
# files never overwrite each other. Every output dir gets:
#   benchmark_results.csv/.json   raw, lossless results
#   benchmark_summary.csv/.json   per (domain, difficulty, algorithm) aggregates
#   analysis/                     curated reports (summary.json,
#                                 by_difficulty_summary.csv,
#                                 human_readable_summary.md, ...)
set -u

echo "=== [1/2] amit suite: all 20 instances, true optimal depths 21-40 (~30-60 min) ==="
python -u main.py --domain puzzle --puzzle-instance-source amit \
  --algorithms astar ilbfs rbfs mp-bfs-best_first mp-rbfs-best_first \
  --output-dir results_amit

echo "=== [2/2] korf sample: optimal depths 41, 47, 55 (ids 55/30/2; measured A* reference, not regression-predicted) (~10-30 min) ==="
python -u main.py --domain puzzle --puzzle-instance-source korf \
  --optimal-depths 41 47 55 \
  --algorithms astar ilbfs rbfs mp-bfs-best_first mp-bfs-round_robin mp-bfs-proportional mp-rbfs-best_first mp-rbfs-round_robin mp-rbfs-proportional \
  --output-dir results_korf

echo "=== Done. Copy results_amit/ and results_korf/ back to the repo. ==="

# Expected behavior on the hard end (amit d>=29, korf d55): A* hits the memory
# ceiling, RBFS-family algorithms hit the node limit -- that is the data point,
# not a bug. Memory ceiling defaults to 80% of total RAM
# (--max-memory-fraction 0.8); lower it if the box is shared.
