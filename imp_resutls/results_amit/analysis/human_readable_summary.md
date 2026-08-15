# Benchmark Results Summary

### Ranking by success rate

1. **A*** -- 1.000
2. **MP-BFS (best_first)** -- 1.000
3. **MP-BFS (proportional)** -- 1.000
4. **MP-BFS (round_robin)** -- 1.000
5. **RBFS** -- 1.000
6. **MP-RBFS (round_robin)** -- 0.750
7. **MP-RBFS (proportional)** -- 0.700
8. **ILBFS** -- 0.600
9. **MP-RBFS (best_first)** -- 0.500

### Ranking by average runtime (solved instances)

1. **A*** -- 1.258
2. **MP-BFS (best_first)** -- 1.745
3. **RBFS** -- 2.541
4. **MP-BFS (round_robin)** -- 2.703
5. **MP-BFS (proportional)** -- 2.887
6. **MP-RBFS (best_first)** -- 7.318
7. **MP-RBFS (proportional)** -- 12.029
8. **MP-RBFS (round_robin)** -- 20.183
9. **ILBFS** -- 21.386

### Ranking by average peak memory

1. **ILBFS** -- 135.848
2. **A*** -- 138.917
3. **MP-BFS (best_first)** -- 145.991
4. **MP-RBFS (proportional)** -- 151.971
5. **MP-RBFS (round_robin)** -- 153.119
6. **MP-RBFS (best_first)** -- 156.804
7. **RBFS** -- 157.765
8. **MP-BFS (round_robin)** -- 164.398
9. **MP-BFS (proportional)** -- 166.337

## Metric notes

- `reexpansion_ratio` and `collapse_ratio` measure the *same* RBFS-family back-up machinery: a node whose children are deleted and later regenerated (ILBFS / mp-rbfs Collapse loop) or whose subtree is explored, backed up, and abandoned (recursive RBFS). Ratios of roughly 1.0 are **normal** for every RBFS-family algorithm -- the search backs up about one node per expansion while walking between branches -- and are **not** a sign of pathology. `collapse_ratio = 0` simply means the algorithm has no collapse machinery (A*, mp-bfs).
- `max proc tree` is reported only by mp-bfs / mp-rbfs: the largest live per-proc search tree observed, confirming the O(b*d) memory bound.

## Per-domain observations

### n_puzzle

- **A***: success 100.0%, avg runtime (solved) 1.258s, avg peak memory 138.917 MB
- **ILBFS**: success 60.0%, avg runtime (solved) 21.386s, avg peak memory 135.848 MB, reexp 500626.550 (44.4% of expanded), collapses 1128334.850 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 1.745s, avg peak memory 145.991 MB, reexp 363.450 (1.2% of expanded)
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 2.887s, avg peak memory 166.337 MB, reexp 1170.750 (2.3% of expanded)
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 2.703s, avg peak memory 164.398 MB, reexp 1170.650 (2.3% of expanded)
- **MP-RBFS (best_first)**: success 50.0%, avg runtime (solved) 7.318s, avg peak memory 156.804 MB, reexp 377912.100 (25.6% of expanded), collapses 1476902.400 (100.0% of expanded), max proc tree 43.200 nodes
- **MP-RBFS (proportional)**: success 70.0%, avg runtime (solved) 12.029s, avg peak memory 151.971 MB, reexp 311686.650 (32.1% of expanded), collapses 971179.200 (99.9% of expanded), max proc tree 44.750 nodes
- **MP-RBFS (round_robin)**: success 75.0%, avg runtime (solved) 20.183s, avg peak memory 153.119 MB, reexp 325481.250 (36.0% of expanded), collapses 902545.450 (99.9% of expanded), max proc tree 45.050 nodes
- **RBFS**: success 100.0%, avg runtime (solved) 2.541s, avg peak memory 157.765 MB, collapses 60493.900 (141.1% of expanded)

## Per-difficulty results

### amit_depth_21 (optimal depth 21)

- **A***: success 100.0%, avg runtime (solved) 0.004s, avg peak memory 20.969 MB, avg expanded 102, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.029s, avg peak memory 20.969 MB, avg expanded 393, avg reexp 157, avg collapses 372 (94.7% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.004s, avg peak memory 20.977 MB, avg expanded 101, avg reexp 4
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.043 MB, avg expanded 101, avg reexp 4
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.043 MB, avg expanded 101, avg reexp 4
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.043 MB, avg expanded 101, avg reexp 4
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.043 MB, avg expanded 101, avg reexp 4
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.043 MB, avg expanded 101, avg reexp 4
- **RBFS**: success 100.0%, avg runtime (solved) 0.007s, avg peak memory 20.977 MB, avg expanded 179, avg reexp 0, avg collapses 198 (110.6% of expanded)

### amit_depth_22 (optimal depth 22)

- **A***: success 100.0%, avg runtime (solved) 0.012s, avg peak memory 21.137 MB, avg expanded 338, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.083s, avg peak memory 21.211 MB, avg expanded 1094, avg reexp 566, avg collapses 1072 (98.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.019s, avg peak memory 21.605 MB, avg expanded 502, avg reexp 0
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.070s, avg peak memory 23.730 MB, avg expanded 1728, avg reexp 5
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.054s, avg peak memory 22.875 MB, avg expanded 1449, avg reexp 4
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.047s, avg peak memory 23.934 MB, avg expanded 689, avg reexp 149, avg collapses 372 (54.0% of expanded), max proc tree 27
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.130s, avg peak memory 23.934 MB, avg expanded 1660, avg reexp 529, avg collapses 1183 (71.3% of expanded), max proc tree 27
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.101s, avg peak memory 23.934 MB, avg expanded 1459, avg reexp 438, avg collapses 1033 (70.8% of expanded), max proc tree 27
- **RBFS**: success 100.0%, avg runtime (solved) 0.022s, avg peak memory 21.336 MB, avg expanded 482, avg reexp 0, avg collapses 644 (133.6% of expanded)

### amit_depth_23 (optimal depth 23)

- **A***: success 100.0%, avg runtime (solved) 0.033s, avg peak memory 23.934 MB, avg expanded 930, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 5.525s, avg peak memory 23.941 MB, avg expanded 63564, avg reexp 22952, avg collapses 63541 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.047s, avg peak memory 24.898 MB, avg expanded 1168, avg reexp 2
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.171s, avg peak memory 29.633 MB, avg expanded 3984, avg reexp 41
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.172s, avg peak memory 29.430 MB, avg expanded 4055, avg reexp 41
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.232s, avg peak memory 29.633 MB, avg expanded 2901, avg reexp 934, avg collapses 2562 (88.3% of expanded), max proc tree 43
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.482s, avg peak memory 29.633 MB, avg expanded 5864, avg reexp 2487, avg collapses 5185 (88.4% of expanded), max proc tree 48
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.486s, avg peak memory 29.633 MB, avg expanded 6085, avg reexp 2639, avg collapses 5405 (88.8% of expanded), max proc tree 48
- **RBFS**: success 100.0%, avg runtime (solved) 0.054s, avg peak memory 24.180 MB, avg expanded 1084, avg reexp 0, avg collapses 1518 (140.0% of expanded)

### amit_depth_24 (optimal depth 24)

- **A***: success 100.0%, avg runtime (solved) 0.085s, avg peak memory 29.633 MB, avg expanded 2197, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.278s, avg peak memory 29.633 MB, avg expanded 3390, avg reexp 1721, avg collapses 3366 (99.3% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.113s, avg peak memory 29.645 MB, avg expanded 2731, avg reexp 18
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.212s, avg peak memory 30.980 MB, avg expanded 5126, avg reexp 84
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.165s, avg peak memory 29.906 MB, avg expanded 3877, avg reexp 62
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 2.961s, avg peak memory 30.984 MB, avg expanded 35510, avg reexp 6652, avg collapses 35043 (98.7% of expanded), max proc tree 45
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.507s, avg peak memory 30.984 MB, avg expanded 6256, avg reexp 2383, avg collapses 5590 (89.4% of expanded), max proc tree 49
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.487s, avg peak memory 30.984 MB, avg expanded 6129, avg reexp 2353, avg collapses 5486 (89.5% of expanded), max proc tree 49
- **RBFS**: success 100.0%, avg runtime (solved) 0.059s, avg peak memory 29.633 MB, avg expanded 1331, avg reexp 0, avg collapses 1785 (134.1% of expanded)

### amit_depth_25 (optimal depth 25)

- **A***: success 100.0%, avg runtime (solved) 0.009s, avg peak memory 30.984 MB, avg expanded 299, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.173s, avg peak memory 30.984 MB, avg expanded 2191, avg reexp 986, avg collapses 2166 (98.9% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.028s, avg peak memory 30.984 MB, avg expanded 773, avg reexp 0
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.035s, avg peak memory 30.984 MB, avg expanded 908, avg reexp 0
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.032s, avg peak memory 30.984 MB, avg expanded 964, avg reexp 0
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.063s, avg peak memory 30.984 MB, avg expanded 922, avg reexp 187, avg collapses 478 (51.8% of expanded), max proc tree 25
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.054s, avg peak memory 30.984 MB, avg expanded 759, avg reexp 105, avg collapses 305 (40.2% of expanded), max proc tree 27
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.068s, avg peak memory 30.984 MB, avg expanded 987, avg reexp 182, avg collapses 493 (49.9% of expanded), max proc tree 22
- **RBFS**: success 100.0%, avg runtime (solved) 0.042s, avg peak memory 30.984 MB, avg expanded 964, avg reexp 0, avg collapses 1190 (123.4% of expanded)

### amit_depth_26 (optimal depth 26)

- **A***: success 100.0%, avg runtime (solved) 0.002s, avg peak memory 30.984 MB, avg expanded 90, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.010s, avg peak memory 30.984 MB, avg expanded 164, avg reexp 59, avg collapses 138 (84.1% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 30.984 MB, avg expanded 89, avg reexp 0
- **RBFS**: success 100.0%, avg runtime (solved) 0.005s, avg peak memory 30.984 MB, avg expanded 122, avg reexp 0, avg collapses 112 (91.8% of expanded)

### amit_depth_27 (optimal depth 27)

- **A***: success 100.0%, avg runtime (solved) 0.014s, avg peak memory 30.984 MB, avg expanded 481, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.123s, avg peak memory 30.984 MB, avg expanded 1569, avg reexp 748, avg collapses 1542 (98.3% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.058s, avg peak memory 30.984 MB, avg expanded 1205, avg reexp 3
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.077s, avg peak memory 30.984 MB, avg expanded 1958, avg reexp 14
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.061s, avg peak memory 30.984 MB, avg expanded 1726, avg reexp 7
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.168s, avg peak memory 30.984 MB, avg expanded 2178, avg reexp 639, avg collapses 1765 (81.0% of expanded), max proc tree 32
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.197s, avg peak memory 30.984 MB, avg expanded 2534, avg reexp 851, avg collapses 1997 (78.8% of expanded), max proc tree 31
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.176s, avg peak memory 30.984 MB, avg expanded 2410, avg reexp 807, avg collapses 1888 (78.3% of expanded), max proc tree 31
- **RBFS**: success 100.0%, avg runtime (solved) 0.048s, avg peak memory 30.984 MB, avg expanded 1083, avg reexp 0, avg collapses 1423 (131.4% of expanded)

### amit_depth_28 (optimal depth 28)

- **A***: success 100.0%, avg runtime (solved) 0.133s, avg peak memory 30.984 MB, avg expanded 3352, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 16.101s, avg peak memory 30.984 MB, avg expanded 182461, avg reexp 88692, avg collapses 182433 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.184s, avg peak memory 36.500 MB, avg expanded 3779, avg reexp 33
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.109s, avg peak memory 36.500 MB, avg expanded 2727, avg reexp 55
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.117s, avg peak memory 36.500 MB, avg expanded 3168, avg reexp 70
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 12.032s, avg peak memory 36.504 MB, avg expanded 135220, avg reexp 53852, avg collapses 134716 (99.6% of expanded), max proc tree 51
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.592s, avg peak memory 36.512 MB, avg expanded 7084, avg reexp 3550, avg collapses 6434 (90.8% of expanded), max proc tree 40
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.475s, avg peak memory 36.504 MB, avg expanded 6102, avg reexp 3245, avg collapses 5445 (89.2% of expanded), max proc tree 40
- **RBFS**: success 100.0%, avg runtime (solved) 0.287s, avg peak memory 33.410 MB, avg expanded 6013, avg reexp 0, avg collapses 8455 (140.6% of expanded)

### amit_depth_29 (optimal depth 29)

- **A***: success 100.0%, avg runtime (solved) 0.039s, avg peak memory 36.512 MB, avg expanded 1091, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 2.329s, avg peak memory 36.512 MB, avg expanded 26272, avg reexp 12962, avg collapses 26243 (99.9% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.100s, avg peak memory 36.512 MB, avg expanded 2019, avg reexp 18
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.190s, avg peak memory 36.512 MB, avg expanded 4610, avg reexp 59
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.204s, avg peak memory 38.516 MB, avg expanded 5402, avg reexp 51
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 36.512 MB, avg expanded 2830907, avg reexp 1383232, avg collapses 2830549 (100.0% of expanded), max proc tree 49
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 38.573s, avg peak memory 40.590 MB, avg expanded 444932, avg reexp 148208, avg collapses 443852 (99.8% of expanded), max proc tree 50
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 36.508s, avg peak memory 39.762 MB, avg expanded 385799, avg reexp 130569, avg collapses 384714 (99.7% of expanded), max proc tree 50
- **RBFS**: success 100.0%, avg runtime (solved) 0.136s, avg peak memory 36.512 MB, avg expanded 2901, avg reexp 0, avg collapses 4061 (140.0% of expanded)

### amit_depth_30 (optimal depth 30)

- **A***: success 100.0%, avg runtime (solved) 0.218s, avg peak memory 37.676 MB, avg expanded 5013, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 37.676 MB, avg expanded 2344300, avg reexp 1029596, avg collapses 2344286 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.479s, avg peak memory 46.344 MB, avg expanded 9827, avg reexp 66
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 1.953s, avg peak memory 99.496 MB, avg expanded 36041, avg reexp 628
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.939s, avg peak memory 65.184 MB, avg expanded 20986, avg reexp 376
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 99.898 MB, avg expanded 2771591, avg reexp 617477, avg collapses 2771143 (100.0% of expanded), max proc tree 55
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 3.403s, avg peak memory 99.898 MB, avg expanded 36583, avg reexp 15791, avg collapses 35684 (97.5% of expanded), max proc tree 55
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 2.956s, avg peak memory 99.898 MB, avg expanded 36567, avg reexp 15714, avg collapses 35682 (97.6% of expanded), max proc tree 55
- **RBFS**: success 100.0%, avg runtime (solved) 0.344s, avg peak memory 39.680 MB, avg expanded 7216, avg reexp 0, avg collapses 9994 (138.5% of expanded)

### amit_depth_31 (optimal depth 31)

- **A***: success 100.0%, avg runtime (solved) 0.010s, avg peak memory 99.898 MB, avg expanded 323, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.058s, avg peak memory 99.898 MB, avg expanded 735, avg reexp 298, avg collapses 704 (95.8% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.035s, avg peak memory 99.898 MB, avg expanded 858, avg reexp 2
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.065s, avg peak memory 99.898 MB, avg expanded 1668, avg reexp 5
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.064s, avg peak memory 99.898 MB, avg expanded 1772, avg reexp 11
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.071s, avg peak memory 99.898 MB, avg expanded 1018, avg reexp 243, avg collapses 629 (61.8% of expanded), max proc tree 39
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 0.177s, avg peak memory 99.898 MB, avg expanded 2382, avg reexp 820, avg collapses 1778 (74.6% of expanded), max proc tree 39
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 0.164s, avg peak memory 99.898 MB, avg expanded 2228, avg reexp 737, avg collapses 1637 (73.5% of expanded), max proc tree 39
- **RBFS**: success 100.0%, avg runtime (solved) 0.017s, avg peak memory 99.898 MB, avg expanded 409, avg reexp 0, avg collapses 453 (110.8% of expanded)

### amit_depth_32 (optimal depth 32)

- **A***: success 100.0%, avg runtime (solved) 0.200s, avg peak memory 99.898 MB, avg expanded 5026, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 10.131s, avg peak memory 99.898 MB, avg expanded 120207, avg reexp 52663, avg collapses 120175 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.391s, avg peak memory 99.906 MB, avg expanded 8676, avg reexp 79
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 0.443s, avg peak memory 84.984 MB, avg expanded 9514, avg reexp 98
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 0.428s, avg peak memory 99.906 MB, avg expanded 9007, avg reexp 106
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 57.598s, avg peak memory 84.984 MB, avg expanded 739230, avg reexp 35384, avg collapses 738455 (99.9% of expanded), max proc tree 54
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 1.537s, avg peak memory 84.988 MB, avg expanded 18120, avg reexp 8705, avg collapses 17342 (95.7% of expanded), max proc tree 48
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 1.440s, avg peak memory 84.984 MB, avg expanded 18082, avg reexp 8835, avg collapses 17275 (95.5% of expanded), max proc tree 48
- **RBFS**: success 100.0%, avg runtime (solved) 0.496s, avg peak memory 99.898 MB, avg expanded 9456, avg reexp 0, avg collapses 12786 (135.2% of expanded)

### amit_depth_33 (optimal depth 33)

- **A***: success 100.0%, avg runtime (solved) 3.569s, avg peak memory 156.047 MB, avg expanded 77527, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 125.195 MB, avg expanded 2558450, avg reexp 1256119, avg collapses 2558438 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.423s, avg peak memory 224.180 MB, avg expanded 78639, avg reexp 802
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 4.067s, avg peak memory 191.496 MB, avg expanded 71618, avg reexp 1399
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 3.792s, avg peak memory 191.227 MB, avg expanded 70341, avg reexp 1453
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 191.688 MB, avg expanded 2763393, avg reexp 1097854, avg collapses 2762715 (100.0% of expanded), max proc tree 46
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 190.715 MB, avg expanded 2848673, avg reexp 1019441, avg collapses 2847565 (100.0% of expanded), max proc tree 53
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 191.688 MB, avg expanded 2846745, avg reexp 1015954, avg collapses 2845642 (100.0% of expanded), max proc tree 53
- **RBFS**: success 100.0%, avg runtime (solved) 6.051s, avg peak memory 215.297 MB, avg expanded 98169, avg reexp 0, avg collapses 148953 (151.7% of expanded)

### amit_depth_34 (optimal depth 34)

- **A***: success 100.0%, avg runtime (solved) 0.238s, avg peak memory 190.715 MB, avg expanded 5931, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 190.715 MB, avg expanded 2374046, avg reexp 1076652, avg collapses 2374028 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.688s, avg peak memory 159.887 MB, avg expanded 13890, avg reexp 97
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 3.466s, avg peak memory 195.051 MB, avg expanded 62823, avg reexp 1587
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 3.552s, avg peak memory 194.336 MB, avg expanded 67375, avg reexp 1666
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 195.051 MB, avg expanded 2602378, avg reexp 723857, avg collapses 2602087 (100.0% of expanded), max proc tree 50
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 187.086 MB, avg expanded 2854073, avg reexp 1323048, avg collapses 2852817 (100.0% of expanded), max proc tree 66
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 195.051 MB, avg expanded 2869407, avg reexp 1072850, avg collapses 2868182 (100.0% of expanded), max proc tree 66
- **RBFS**: success 100.0%, avg runtime (solved) 0.552s, avg peak memory 190.715 MB, avg expanded 9857, avg reexp 0, avg collapses 13176 (133.7% of expanded)

### amit_depth_35 (optimal depth 35)

- **A***: success 100.0%, avg runtime (solved) 0.747s, avg peak memory 187.086 MB, avg expanded 17277, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 221.787s, avg peak memory 187.086 MB, avg expanded 2597632, avg reexp 1046153, avg collapses 2597597 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.986s, avg peak memory 189.004 MB, avg expanded 18045, avg reexp 65
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 1.044s, avg peak memory 181.207 MB, avg expanded 20990, avg reexp 328
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 1.055s, avg peak memory 182.191 MB, avg expanded 21507, avg reexp 331
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 181.207 MB, avg expanded 2650621, avg reexp 458055, avg collapses 2650200 (100.0% of expanded), max proc tree 59
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 116.053s, avg peak memory 181.207 MB, avg expanded 1255487, avg reexp 441745, avg collapses 1254299 (99.9% of expanded), max proc tree 62
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 103.626s, avg peak memory 181.207 MB, avg expanded 1192553, avg reexp 481880, avg collapses 1191355 (99.9% of expanded), max proc tree 62
- **RBFS**: success 100.0%, avg runtime (solved) 2.966s, avg peak memory 187.086 MB, avg expanded 52223, avg reexp 0, avg collapses 70743 (135.5% of expanded)

### amit_depth_36 (optimal depth 36)

- **A***: success 100.0%, avg runtime (solved) 2.713s, avg peak memory 182.117 MB, avg expanded 58806, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 182.117 MB, avg expanded 2539989, avg reexp 893780, avg collapses 2539965 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 3.720s, avg peak memory 232.324 MB, avg expanded 66012, avg reexp 630
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 12.411s, avg peak memory 498.926 MB, avg expanded 209940, avg reexp 4365
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 11.589s, avg peak memory 483.145 MB, avg expanded 205616, avg reexp 4279
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 434.941 MB, avg expanded 2941724, avg reexp 646173, avg collapses 2941267 (100.0% of expanded), max proc tree 56
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 434.941 MB, avg expanded 2829628, avg reexp 864501, avg collapses 2828361 (100.0% of expanded), max proc tree 61
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 434.941 MB, avg expanded 2823498, avg reexp 867255, avg collapses 2822231 (100.0% of expanded), max proc tree 61
- **RBFS**: success 100.0%, avg runtime (solved) 6.061s, avg peak memory 255.766 MB, avg expanded 100647, avg reexp 0, avg collapses 140220 (139.3% of expanded)

### amit_depth_37 (optimal depth 37)

- **A***: success 100.0%, avg runtime (solved) 3.006s, avg peak memory 434.953 MB, avg expanded 68295, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 434.953 MB, avg expanded 2336935, avg reexp 958729, avg collapses 2336913 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 3.763s, avg peak memory 323.395 MB, avg expanded 67644, avg reexp 534
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 3.396s, avg peak memory 314.535 MB, avg expanded 60650, avg reexp 1147
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 3.484s, avg peak memory 315.520 MB, avg expanded 63652, avg reexp 1237
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 314.539 MB, avg expanded 2522340, avg reexp 808320, avg collapses 2521850 (100.0% of expanded), max proc tree 58
- **MP-RBFS (proportional)**: success 100.0%, avg runtime (solved) 6.695s, avg peak memory 314.539 MB, avg expanded 76365, avg reexp 34309, avg collapses 75296 (98.6% of expanded), max proc tree 59
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 22.665s, avg peak memory 314.539 MB, avg expanded 261328, avg reexp 111299, avg collapses 260212 (99.6% of expanded), max proc tree 59
- **RBFS**: success 100.0%, avg runtime (solved) 3.941s, avg peak memory 434.953 MB, avg expanded 67977, avg reexp 0, avg collapses 92463 (136.0% of expanded)

### amit_depth_38 (optimal depth 38)

- **A***: success 100.0%, avg runtime (solved) 8.352s, avg peak memory 359.598 MB, avg expanded 180232, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 328.996 MB, avg expanded 2443227, avg reexp 1236538, avg collapses 2443215 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 10.497s, avg peak memory 504.836 MB, avg expanded 181780, avg reexp 2252
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 14.054s, avg peak memory 546.746 MB, avg expanded 243416, avg reexp 6579
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 13.660s, avg peak memory 545.730 MB, avg expanded 242777, avg reexp 6747
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 483.043 MB, avg expanded 3294215, avg reexp 617780, avg collapses 3293521 (100.0% of expanded), max proc tree 57
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 405.090 MB, avg expanded 3018612, avg reexp 852411, avg collapses 3017463 (100.0% of expanded), max proc tree 54
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 406.074 MB, avg expanded 3014285, avg reexp 1278058, avg collapses 3013170 (100.0% of expanded), max proc tree 54
- **RBFS**: success 100.0%, avg runtime (solved) 16.040s, avg peak memory 554.539 MB, avg expanded 267506, avg reexp 0, avg collapses 381235 (142.5% of expanded)

### amit_depth_39 (optimal depth 39)

- **A***: success 100.0%, avg runtime (solved) 3.433s, avg peak memory 404.090 MB, avg expanded 81213, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 404.090 MB, avg expanded 2486646, avg reexp 1283145, avg collapses 2486621 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.504s, avg peak memory 362.609 MB, avg expanded 82443, avg reexp 1881
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 6.856s, avg peak memory 402.047 MB, avg expanded 118859, avg reexp 4188
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 6.242s, avg peak memory 401.395 MB, avg expanded 118192, avg reexp 4073
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 370.121 MB, avg expanded 3333234, avg reexp 330810, avg collapses 3332622 (100.0% of expanded), max proc tree 51
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 370.125 MB, avg expanded 3229097, avg reexp 600191, avg collapses 3227990 (100.0% of expanded), max proc tree 64
- **MP-RBFS (round_robin)**: success 100.0%, avg runtime (solved) 133.595s, avg peak memory 370.125 MB, avg expanded 1796182, avg reexp 386646, avg collapses 1795145 (99.9% of expanded), max proc tree 75
- **RBFS**: success 100.0%, avg runtime (solved) 5.905s, avg peak memory 404.090 MB, avg expanded 98917, avg reexp 0, avg collapses 138979 (140.5% of expanded)

### amit_depth_40 (optimal depth 40)

- **A***: success 100.0%, avg runtime (solved) 2.347s, avg peak memory 370.133 MB, avg expanded 54826, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 370.133 MB, avg expanded 2483897, avg reexp 1050015, avg collapses 2483882 (100.0% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.848s, avg peak memory 414.344 MB, avg expanded 86754, avg reexp 783
- **MP-BFS (proportional)**: success 100.0%, avg runtime (solved) 9.122s, avg peak memory 441.000 MB, avg expanded 159918, avg reexp 2829
- **MP-BFS (round_robin)**: success 100.0%, avg runtime (solved) 8.440s, avg peak memory 438.207 MB, avg expanded 156754, avg reexp 2895
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 409.148 MB, avg expanded 2918499, avg reexp 776640, avg collapses 2918074 (100.0% of expanded), max proc tree 67
- **MP-RBFS (proportional)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 395.285 MB, avg expanded 2801718, avg reexp 914654, avg collapses 2800443 (100.0% of expanded), max proc tree 62
- **MP-RBFS (round_robin)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 409.160 MB, avg expanded 2797190, avg reexp 1130160, avg collapses 2795914 (100.0% of expanded), max proc tree 62
- **RBFS**: success 100.0%, avg runtime (solved) 7.784s, avg peak memory 414.387 MB, avg expanded 131035, avg reexp 0, avg collapses 181490 (138.5% of expanded)

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.914.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
