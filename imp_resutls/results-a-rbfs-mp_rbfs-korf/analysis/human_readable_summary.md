# Benchmark Results Summary

### Ranking by success rate

1. **A*** -- 1.000
2. **mp-rbfs-best_first** -- 1.000
3. **mp-rbfs-proportional** -- 1.000
4. **mp-rbfs-round_robin** -- 1.000
5. **rbfs** -- 1.000

### Ranking by average runtime (solved instances)

1. **A*** -- 14.433
2. **mp-rbfs-best_first** -- 16.101
3. **rbfs** -- 16.482
4. **mp-rbfs-round_robin** -- 18.553
5. **mp-rbfs-proportional** -- 19.468

### Ranking by average peak memory

1. **rbfs** -- 797.502
2. **mp-rbfs-best_first** -- 822.371
3. **A*** -- 845.907
4. **mp-rbfs-proportional** -- 911.799
5. **mp-rbfs-round_robin** -- 929.896

## Per-domain observations

### n_puzzle

- **A***: success 100.0%, avg runtime (solved) 14.433s, avg peak memory 845.907 MB
- **mp-rbfs-best_first**: success 100.0%, avg runtime (solved) 16.101s, avg peak memory 822.371 MB
- **mp-rbfs-proportional**: success 100.0%, avg runtime (solved) 19.468s, avg peak memory 911.799 MB
- **mp-rbfs-round_robin**: success 100.0%, avg runtime (solved) 18.553s, avg peak memory 929.896 MB
- **rbfs**: success 100.0%, avg runtime (solved) 16.482s, avg peak memory 797.502 MB

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.873.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: rbfs.
