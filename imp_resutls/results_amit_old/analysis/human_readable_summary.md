# Benchmark Results Summary

### Ranking by success rate

1. **A*** -- 1.000
2. **MP-BFS (best_first)** -- 1.000
3. **RBFS** -- 1.000
4. **ILBFS** -- 0.600
5. **MP-RBFS (best_first)** -- 0.500

### Ranking by average runtime (solved instances)

1. **A*** -- 1.230
2. **MP-BFS (best_first)** -- 1.750
3. **RBFS** -- 2.435
4. **MP-RBFS (best_first)** -- 7.298
5. **ILBFS** -- 20.836

### Ranking by average peak memory

1. **ILBFS** -- 106.780
2. **A*** -- 112.237
3. **MP-RBFS (best_first)** -- 116.078
4. **MP-BFS (best_first)** -- 131.270
5. **RBFS** -- 133.024

## Metric notes

- `reexpansion_ratio` and `collapse_ratio` measure the *same* RBFS-family back-up machinery: a node whose children are deleted and later regenerated (ILBFS / mp-rbfs Collapse loop) or whose subtree is explored, backed up, and abandoned (recursive RBFS). Ratios of roughly 1.0 are **normal** for every RBFS-family algorithm -- the search backs up about one node per expansion while walking between branches -- and are **not** a sign of pathology. `collapse_ratio = 0` simply means the algorithm has no collapse machinery (A*, mp-bfs).
- `max proc tree` is reported only by mp-bfs / mp-rbfs: the largest live per-proc search tree observed, confirming the O(b*d) memory bound.

## Per-domain observations

### n_puzzle

- **A***: success 100.0%, avg runtime (solved) 1.230s, avg peak memory 112.237 MB
- **ILBFS**: success 60.0%, avg runtime (solved) 20.836s, avg peak memory 106.780 MB, reexp 500626.550 (44.4% of expanded)
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 1.750s, avg peak memory 131.270 MB, reexp 363.450 (1.2% of expanded)
- **MP-RBFS (best_first)**: success 50.0%, avg runtime (solved) 7.298s, avg peak memory 116.078 MB, reexp 377912.100 (25.6% of expanded), collapses 1476902.400 (100.0% of expanded), max proc tree 43.200 nodes
- **RBFS**: success 100.0%, avg runtime (solved) 2.435s, avg peak memory 133.024 MB

## Per-difficulty results

### amit_depth_21 (optimal depth 21)

- **A***: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 20.902 MB, avg expanded 102, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.028s, avg peak memory 20.961 MB, avg expanded 393, avg reexp 157
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.004s, avg peak memory 21.000 MB, avg expanded 101, avg reexp 4
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 21.070 MB, avg expanded 101, avg reexp 4
- **RBFS**: success 100.0%, avg runtime (solved) 0.007s, avg peak memory 20.965 MB, avg expanded 179, avg reexp 0

### amit_depth_22 (optimal depth 22)

- **A***: success 100.0%, avg runtime (solved) 0.012s, avg peak memory 21.168 MB, avg expanded 338, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.080s, avg peak memory 21.242 MB, avg expanded 1094, avg reexp 566
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.020s, avg peak memory 21.637 MB, avg expanded 502, avg reexp 0
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.048s, avg peak memory 21.887 MB, avg expanded 689, avg reexp 149, avg collapses 372 (54.0% of expanded), max proc tree 27
- **RBFS**: success 100.0%, avg runtime (solved) 0.021s, avg peak memory 21.371 MB, avg expanded 482, avg reexp 0

### amit_depth_23 (optimal depth 23)

- **A***: success 100.0%, avg runtime (solved) 0.035s, avg peak memory 22.160 MB, avg expanded 930, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 5.277s, avg peak memory 22.160 MB, avg expanded 63564, avg reexp 22952
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.043s, avg peak memory 23.023 MB, avg expanded 1168, avg reexp 2
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.224s, avg peak memory 23.023 MB, avg expanded 2901, avg reexp 934, avg collapses 2562 (88.3% of expanded), max proc tree 43
- **RBFS**: success 100.0%, avg runtime (solved) 0.047s, avg peak memory 22.590 MB, avg expanded 1084, avg reexp 0

### amit_depth_24 (optimal depth 24)

- **A***: success 100.0%, avg runtime (solved) 0.082s, avg peak memory 23.418 MB, avg expanded 2197, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.271s, avg peak memory 23.418 MB, avg expanded 3390, avg reexp 1721
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.106s, avg peak memory 27.039 MB, avg expanded 2731, avg reexp 18
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 2.663s, avg peak memory 27.258 MB, avg expanded 35510, avg reexp 6652, avg collapses 35043 (98.7% of expanded), max proc tree 45
- **RBFS**: success 100.0%, avg runtime (solved) 0.057s, avg peak memory 23.617 MB, avg expanded 1331, avg reexp 0

### amit_depth_25 (optimal depth 25)

- **A***: success 100.0%, avg runtime (solved) 0.009s, avg peak memory 27.258 MB, avg expanded 299, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.166s, avg peak memory 27.258 MB, avg expanded 2191, avg reexp 986
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.035s, avg peak memory 27.258 MB, avg expanded 773, avg reexp 0
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.067s, avg peak memory 27.258 MB, avg expanded 922, avg reexp 187, avg collapses 478 (51.8% of expanded), max proc tree 25
- **RBFS**: success 100.0%, avg runtime (solved) 0.055s, avg peak memory 27.258 MB, avg expanded 964, avg reexp 0

### amit_depth_26 (optimal depth 26)

- **A***: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 27.258 MB, avg expanded 90, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.010s, avg peak memory 27.258 MB, avg expanded 164, avg reexp 59
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 27.258 MB, avg expanded 89, avg reexp 0
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.003s, avg peak memory 27.258 MB, avg expanded 89, avg reexp 0
- **RBFS**: success 100.0%, avg runtime (solved) 0.005s, avg peak memory 27.258 MB, avg expanded 122, avg reexp 0

### amit_depth_27 (optimal depth 27)

- **A***: success 100.0%, avg runtime (solved) 0.016s, avg peak memory 27.258 MB, avg expanded 481, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.121s, avg peak memory 27.258 MB, avg expanded 1569, avg reexp 748
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.045s, avg peak memory 27.258 MB, avg expanded 1205, avg reexp 3
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.160s, avg peak memory 27.258 MB, avg expanded 2178, avg reexp 639, avg collapses 1765 (81.0% of expanded), max proc tree 32
- **RBFS**: success 100.0%, avg runtime (solved) 0.046s, avg peak memory 27.258 MB, avg expanded 1083, avg reexp 0

### amit_depth_28 (optimal depth 28)

- **A***: success 100.0%, avg runtime (solved) 0.132s, avg peak memory 27.684 MB, avg expanded 3352, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 15.574s, avg peak memory 27.723 MB, avg expanded 182461, avg reexp 88692
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.183s, avg peak memory 36.570 MB, avg expanded 3779, avg reexp 33
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 12.170s, avg peak memory 36.574 MB, avg expanded 135220, avg reexp 53852, avg collapses 134716 (99.6% of expanded), max proc tree 51
- **RBFS**: success 100.0%, avg runtime (solved) 0.276s, avg peak memory 34.098 MB, avg expanded 6013, avg reexp 0

### amit_depth_29 (optimal depth 29)

- **A***: success 100.0%, avg runtime (solved) 0.039s, avg peak memory 35.574 MB, avg expanded 1091, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 2.272s, avg peak memory 35.574 MB, avg expanded 26272, avg reexp 12962
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.084s, avg peak memory 35.574 MB, avg expanded 2019, avg reexp 18
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 35.574 MB, avg expanded 2830907, avg reexp 1383232, avg collapses 2830549 (100.0% of expanded), max proc tree 49
- **RBFS**: success 100.0%, avg runtime (solved) 0.129s, avg peak memory 35.574 MB, avg expanded 2901, avg reexp 0

### amit_depth_30 (optimal depth 30)

- **A***: success 100.0%, avg runtime (solved) 0.197s, avg peak memory 35.582 MB, avg expanded 5013, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 35.582 MB, avg expanded 2344300, avg reexp 1029596
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.454s, avg peak memory 48.492 MB, avg expanded 9827, avg reexp 66
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 48.699 MB, avg expanded 2771591, avg reexp 617477, avg collapses 2771143 (100.0% of expanded), max proc tree 55
- **RBFS**: success 100.0%, avg runtime (solved) 0.369s, avg peak memory 37.719 MB, avg expanded 7216, avg reexp 0

### amit_depth_31 (optimal depth 31)

- **A***: success 100.0%, avg runtime (solved) 0.010s, avg peak memory 48.699 MB, avg expanded 323, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 0.057s, avg peak memory 48.699 MB, avg expanded 735, avg reexp 298
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.035s, avg peak memory 48.699 MB, avg expanded 858, avg reexp 2
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 0.071s, avg peak memory 48.699 MB, avg expanded 1018, avg reexp 243, avg collapses 629 (61.8% of expanded), max proc tree 39
- **RBFS**: success 100.0%, avg runtime (solved) 0.016s, avg peak memory 48.699 MB, avg expanded 409, avg reexp 0

### amit_depth_32 (optimal depth 32)

- **A***: success 100.0%, avg runtime (solved) 0.201s, avg peak memory 48.699 MB, avg expanded 5026, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 9.876s, avg peak memory 48.699 MB, avg expanded 120207, avg reexp 52663
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.396s, avg peak memory 49.402 MB, avg expanded 8676, avg reexp 79
- **MP-RBFS (best_first)**: success 100.0%, avg runtime (solved) 57.571s, avg peak memory 49.621 MB, avg expanded 739230, avg reexp 35384, avg collapses 738455 (99.9% of expanded), max proc tree 54
- **RBFS**: success 100.0%, avg runtime (solved) 0.452s, avg peak memory 48.715 MB, avg expanded 9456, avg reexp 0

### amit_depth_33 (optimal depth 33)

- **A***: success 100.0%, avg runtime (solved) 3.653s, avg peak memory 155.633 MB, avg expanded 77527, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 115.762 MB, avg expanded 2558450, avg reexp 1256119
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.445s, avg peak memory 224.223 MB, avg expanded 78639, avg reexp 802
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 190.816 MB, avg expanded 2763393, avg reexp 1097854, avg collapses 2762715 (100.0% of expanded), max proc tree 46
- **RBFS**: success 100.0%, avg runtime (solved) 5.804s, avg peak memory 214.867 MB, avg expanded 98169, avg reexp 0

### amit_depth_34 (optimal depth 34)

- **A***: success 100.0%, avg runtime (solved) 0.241s, avg peak memory 189.832 MB, avg expanded 5931, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 189.832 MB, avg expanded 2374046, avg reexp 1076652
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.683s, avg peak memory 189.832 MB, avg expanded 13890, avg reexp 97
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 175.027 MB, avg expanded 2602378, avg reexp 723857, avg collapses 2602087 (100.0% of expanded), max proc tree 50
- **RBFS**: success 100.0%, avg runtime (solved) 0.447s, avg peak memory 189.832 MB, avg expanded 9857, avg reexp 0

### amit_depth_35 (optimal depth 35)

- **A***: success 100.0%, avg runtime (solved) 0.733s, avg peak memory 170.074 MB, avg expanded 17277, avg reexp 0
- **ILBFS**: success 100.0%, avg runtime (solved) 216.297s, avg peak memory 170.074 MB, avg expanded 2597632, avg reexp 1046153
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 0.983s, avg peak memory 184.277 MB, avg expanded 18045, avg reexp 65
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 168.078 MB, avg expanded 2650621, avg reexp 458055, avg collapses 2650200 (100.0% of expanded), max proc tree 59
- **RBFS**: success 100.0%, avg runtime (solved) 2.964s, avg peak memory 173.043 MB, avg expanded 52223, avg reexp 0

### amit_depth_36 (optimal depth 36)

- **A***: success 100.0%, avg runtime (solved) 2.752s, avg peak memory 167.078 MB, avg expanded 58806, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 166.090 MB, avg expanded 2539989, avg reexp 893780
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 3.733s, avg peak memory 226.469 MB, avg expanded 66012, avg reexp 630
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 192.621 MB, avg expanded 2941724, avg reexp 646173, avg collapses 2941267 (100.0% of expanded), max proc tree 56
- **RBFS**: success 100.0%, avg runtime (solved) 5.813s, avg peak memory 249.684 MB, avg expanded 100647, avg reexp 0

### amit_depth_37 (optimal depth 37)

- **A***: success 100.0%, avg runtime (solved) 2.984s, avg peak memory 192.637 MB, avg expanded 68295, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 192.637 MB, avg expanded 2336935, avg reexp 958729
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 3.701s, avg peak memory 206.527 MB, avg expanded 67644, avg reexp 534
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 196.617 MB, avg expanded 2522340, avg reexp 808320, avg collapses 2521850 (100.0% of expanded), max proc tree 58
- **RBFS**: success 100.0%, avg runtime (solved) 3.772s, avg peak memory 194.121 MB, avg expanded 67977, avg reexp 0

### amit_depth_38 (optimal depth 38)

- **A***: success 100.0%, avg runtime (solved) 7.647s, avg peak memory 323.473 MB, avg expanded 180232, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 255.016 MB, avg expanded 2443227, avg reexp 1236538
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 10.524s, avg peak memory 502.414 MB, avg expanded 181780, avg reexp 2252
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 362.395 MB, avg expanded 3294215, avg reexp 617780, avg collapses 3293521 (100.0% of expanded), max proc tree 57
- **RBFS**: success 100.0%, avg runtime (solved) 15.497s, avg peak memory 553.945 MB, avg expanded 267506, avg reexp 0

### amit_depth_39 (optimal depth 39)

- **A***: success 100.0%, avg runtime (solved) 3.482s, avg peak memory 361.410 MB, avg expanded 81213, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 361.410 MB, avg expanded 2486646, avg reexp 1283145
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.610s, avg peak memory 336.695 MB, avg expanded 82443, avg reexp 1881
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 319.926 MB, avg expanded 3333234, avg reexp 330810, avg collapses 3332622 (100.0% of expanded), max proc tree 51
- **RBFS**: success 100.0%, avg runtime (solved) 5.506s, avg peak memory 361.410 MB, avg expanded 98917, avg reexp 0

### amit_depth_40 (optimal depth 40)

- **A***: success 100.0%, avg runtime (solved) 2.360s, avg peak memory 318.941 MB, avg expanded 54826, avg reexp 0
- **ILBFS**: success 0.0%, avg runtime (solved) n/as, avg peak memory 318.941 MB, avg expanded 2483897, avg reexp 1050015
- **MP-BFS (best_first)**: success 100.0%, avg runtime (solved) 4.921s, avg peak memory 361.758 MB, avg expanded 86754, avg reexp 783
- **MP-RBFS (best_first)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 321.895 MB, avg expanded 2918499, avg reexp 776640, avg collapses 2918074 (100.0% of expanded), max proc tree 67
- **RBFS**: success 100.0%, avg runtime (solved) 7.425s, avg peak memory 348.461 MB, avg expanded 131035, avg reexp 0

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.000.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
