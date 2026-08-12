# Benchmark Results Summary

### Ranking by success rate

1. **A*** -- 1.000
2. **rbfs** -- 1.000
3. **ILBFS** -- 0.600

### Ranking by average runtime (solved instances)

1. **A*** -- 1.274
2. **rbfs** -- 2.490
3. **ILBFS** -- 20.317

### Ranking by average peak memory

1. **ILBFS** -- 127.861
2. **A*** -- 135.817
3. **rbfs** -- 148.948

## Per-domain observations

### n_puzzle

- **A***: success 100.0%, avg runtime (solved) 1.274s, avg peak memory 135.817 MB
- **ILBFS**: success 60.0%, avg runtime (solved) 20.317s, avg peak memory 127.861 MB
- **rbfs**: success 100.0%, avg runtime (solved) 2.490s, avg peak memory 148.948 MB

## Tradeoff discussion

- **Runtime**: see runtime ranking above.
- **RAM usage**: see peak-memory ranking above.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.000.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
