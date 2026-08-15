# Benchmark Results Summary

### Ranking by success rate

1. **MP-BFS (best_first)** -- 1.000
2. **MP-BFS (proportional)** -- 1.000
3. **MP-BFS (round_robin)** -- 1.000
4. **A*** -- 0.667
5. **RBFS** -- 0.667
6. **MP-RBFS (best_first)** -- 0.000
7. **MP-RBFS (proportional)** -- 0.000
8. **MP-RBFS (round_robin)** -- 0.000

### Ranking by average runtime (solved instances)

1. **A*** -- 8.371
2. **RBFS** -- 20.825
3. **MP-BFS (round_robin)** -- 44.200
4. **MP-BFS (proportional)** -- 47.450
5. **MP-BFS (best_first)** -- 50.430

### Ranking by average peak memory

1. **A*** -- 1728.349
2. **MP-RBFS (proportional)** -- 1742.342
3. **MP-RBFS (round_robin)** -- 1744.967
4. **MP-RBFS (best_first)** -- 1758.742
5. **MP-BFS (proportional)** -- 2041.152
6. **MP-BFS (round_robin)** -- 2050.681
7. **MP-BFS (best_first)** -- 2152.259
8. **RBFS** -- 2223.904

## Metric notes

- `reexpansion_ratio` and `collapse_ratio` measure the *same* RBFS-family back-up machinery: a node whose children are deleted and later regenerated (ILBFS / mp-rbfs Collapse loop) or whose subtree is explored, backed up, and abandoned (recursive RBFS). Ratios of roughly 1.0 are **normal** for every RBFS-family algorithm -- the search backs up about one node per expansion while walking between branches -- and are **not** a sign of pathology. `collapse_ratio = 0` simply means the algorithm has no collapse machinery (A*, mp-bfs).
- `max proc tree` is reported only by mp-bfs / mp-rbfs: the largest live per-proc search tree observed, confirming the O(b*d) memory bound.

## Per-domain observations

### n_puzzle

- **A***: success 66.7%, avg runtime (solved) 8.371s, avg peak memory 1728.349 MB
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 50.430s, avg peak memory 2152.259 MB, reexp 8714.000 (1.0% of expanded)
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 47.450s, avg peak memory 2041.152 MB, reexp 15553.333 (2.0% of expanded)
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 44.200s, avg peak memory 2050.681 MB, reexp 15357.667 (2.0% of expanded)
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 1758.742 MB, reexp 616356.333 (22.4% of expanded), collapses 2755648.667 (100.0% of expanded), max proc tree 66.667 nodes
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 1742.342 MB, reexp 985571.000 (34.9% of expanded), collapses 2823921.333 (100.0% of expanded), max proc tree 71.667 nodes
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 1744.967 MB, reexp 1048405.000 (37.1% of expanded), collapses 2826078.000 (100.0% of expanded), max proc tree 71.667 nodes
- **RBFS**: success 66.7%, avg runtime (solved) 20.825s, avg peak memory 2223.904 MB, collapses 1393871.667 (121.0% of expanded)

## Per-difficulty results

### korf_depth_41 (optimal depth 41)

- **A***: success 100.0%, avg runtime (solved) 6.772s, avg peak memory 276.391 MB, avg expanded 144591, avg reexp 0
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 7.093s, avg peak memory 326.566 MB, avg expanded 126528, avg reexp 925
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 6.873s, avg peak memory 316.441 MB, avg expanded 120339, avg reexp 1631
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 6.839s, avg peak memory 315.543 MB, avg expanded 126860, avg reexp 1799
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 284.445 MB, avg expanded 2502582, avg reexp 837889, avg collapses 2502213 (100.0% of expanded), max proc tree 63
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 276.582 MB, avg expanded 2775806, avg reexp 963530, avg collapses 2774504 (100.0% of expanded), max proc tree 66
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 284.457 MB, avg expanded 2782022, avg reexp 962336, avg collapses 2780675 (100.0% of expanded), max proc tree 66
- **RBFS**: success 100.0%, avg runtime (solved) 10.062s, avg peak memory 354.602 MB, avg expanded 171012, avg reexp 0, avg collapses 229843 (134.4% of expanded)

### korf_depth_47 (optimal depth 47)

- **A***: success 100.0%, avg runtime (solved) 9.970s, avg peak memory 397.039 MB, avg expanded 218817, avg reexp 0
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 19.127s, avg peak memory 991.027 MB, avg expanded 322163, avg reexp 2459
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 76.832s, avg peak memory 2646.824 MB, avg expanded 1270519, avg reexp 24061
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 77.642s, avg peak memory 2754.125 MB, avg expanded 1330634, avg reexp 25610
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2128.270 MB, avg expanded 2569501, avg reexp 629774, avg collapses 2569164 (100.0% of expanded), max proc tree 74
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2106.629 MB, avg expanded 2696566, avg reexp 1038624, avg collapses 2695265 (100.0% of expanded), max proc tree 74
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2106.629 MB, avg expanded 2701606, avg reexp 1008154, avg collapses 2700333 (100.0% of expanded), max proc tree 74
- **RBFS**: success 100.0%, avg runtime (solved) 31.587s, avg peak memory 1099.684 MB, avg expanded 540979, avg reexp 0, avg collapses 681080 (125.9% of expanded)

### korf_depth_55 (optimal depth 55)

- **A***: success 0.0%, avg runtime (solved) n/as, avg peak memory 4511.617 MB, avg expanded 2678075, avg reexp 0
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 125.071s, avg peak memory 5139.184 MB, avg expanded 2219586, avg reexp 22758
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 58.645s, avg peak memory 3160.191 MB, avg expanded 976212, avg reexp 20968
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 48.119s, avg peak memory 3082.375 MB, avg expanded 887907, avg reexp 18664
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2863.512 MB, avg expanded 3196021, avg reexp 381406, avg collapses 3195569 (100.0% of expanded), max proc tree 63
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2843.816 MB, avg expanded 3003554, avg reexp 954559, avg collapses 3001995 (99.9% of expanded), max proc tree 75
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2843.816 MB, avg expanded 2998808, avg reexp 1174725, avg collapses 2997226 (99.9% of expanded), max proc tree 75
- **RBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 5217.426 MB, avg expanded 2744179, avg reexp 0, avg collapses 3270692 (119.2% of expanded)

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 1.200.

## Conclusion

- **Strongest overall (by success rate)**: MP-BFS (best_first).
- **Strongest under memory pressure (by avg peak memory)**: A*.
