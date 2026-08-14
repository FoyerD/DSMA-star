# Benchmark Results Summary

### Ranking by success rate

1. **MP-BFS (best_first)** -- 1.000
2. **A*** -- 0.667
3. **RBFS** -- 0.667
4. **ILBFS** -- 0.000
5. **MP-RBFS (best_first)** -- 0.000

### Ranking by average runtime (solved instances)

1. **A*** -- 7.932
2. **RBFS** -- 19.885
3. **MP-BFS (best_first)** -- 49.733

### Ranking by average peak memory

1. **ILBFS** -- 848.155
2. **MP-RBFS (best_first)** -- 1204.068
3. **A*** -- 1727.392
4. **MP-BFS (best_first)** -- 2132.230
5. **RBFS** -- 2223.621

## Per-domain observations

### n_puzzle

- **A***: success 66.7%, avg runtime (solved) 7.932s, avg peak memory 1727.392 MB
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 848.155 MB, reexp 1039443.000 (41.9% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 49.733s, avg peak memory 2132.230 MB, reexp 8714.000 (1.0% of expanded)
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 1204.068 MB, reexp 616356.333 (22.4% of expanded), collapses 2755648.667 (100.0% of expanded), max proc tree 66.667 nodes
- **RBFS**: success 66.7%, avg runtime (solved) 19.885s, avg peak memory 2223.621 MB

## Per-difficulty results

### korf_depth_41 (optimal depth 41)

- **A***: success 100.0%, avg runtime (solved) 6.715s, avg peak memory 276.152 MB, avg expanded 144591, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 178.840 MB, avg expanded 2533687, avg reexp 995541
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 7.105s, avg peak memory 326.344 MB, avg expanded 126528, avg reexp 925
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 282.332 MB, avg expanded 2502582, avg reexp 837889, avg collapses 2502213, max proc tree 63
- **RBFS**: success 100.0%, avg runtime (solved) 9.653s, avg peak memory 354.387 MB, avg expanded 171012, avg reexp 0

### korf_depth_47 (optimal depth 47)

- **A***: success 100.0%, avg runtime (solved) 9.149s, avg peak memory 397.383 MB, avg expanded 218817, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 305.703 MB, avg expanded 2397405, avg reexp 1041697
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 19.043s, avg peak memory 991.172 MB, avg expanded 322163, avg reexp 2459
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 614.945 MB, avg expanded 2569501, avg reexp 629774, avg collapses 2569164, max proc tree 74
- **RBFS**: success 100.0%, avg runtime (solved) 30.118s, avg peak memory 1099.371 MB, avg expanded 540979, avg reexp 0

### korf_depth_55 (optimal depth 55)

- **A***: success 0.0%, avg runtime (solved) n/as, avg peak memory 4508.641 MB, avg expanded 2678075, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2059.922 MB, avg expanded 2510683, avg reexp 1081091
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 123.052s, avg peak memory 5079.176 MB, avg expanded 2219586, avg reexp 22758
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 2714.926 MB, avg expanded 3196021, avg reexp 381406, avg collapses 3195569, max proc tree 63
- **RBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 5217.105 MB, avg expanded 2744179, avg reexp 0

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.000.

## Conclusion

- **Strongest overall (by success rate)**: MP-BFS (best_first).
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
