# Benchmark Results Summary

### Ranking by success rate

1. **A*** -- 1.000
2. **mp-rbfs-best_first** -- 1.000
3. **mp-rbfs-proportional** -- 1.000
4. **mp-rbfs-round_robin** -- 1.000
5. **rbfs** -- 1.000
6. **ILBFS** -- 0.600

### Ranking by average runtime (solved instances)

1. **A*** -- 1.206
2. **mp-rbfs-best_first** -- 1.531
3. **mp-rbfs-proportional** -- 2.034
4. **mp-rbfs-round_robin** -- 2.083
5. **rbfs** -- 2.421
6. **ILBFS** -- 21.086

### Ranking by average peak memory

1. **ILBFS** -- 117.748
2. **A*** -- 123.683
3. **mp-rbfs-proportional** -- 137.413
4. **mp-rbfs-best_first** -- 137.575
5. **mp-rbfs-round_robin** -- 139.591
6. **rbfs** -- 144.419

## Per-domain observations

### n_puzzle

- **A***: success 100.0%, avg runtime (solved) 1.206s, avg peak memory 123.683 MB
- **ILBFS**: success 60.0%, avg runtime (solved) 21.086s, avg peak memory 117.748 MB
- **mp-rbfs-best_first**: success 100.0%, avg runtime (solved) 1.531s, avg peak memory 137.575 MB
- **mp-rbfs-proportional**: success 100.0%, avg runtime (solved) 2.034s, avg peak memory 137.413 MB
- **mp-rbfs-round_robin**: success 100.0%, avg runtime (solved) 2.083s, avg peak memory 139.591 MB
- **rbfs**: success 100.0%, avg runtime (solved) 2.421s, avg peak memory 144.419 MB

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.464.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
