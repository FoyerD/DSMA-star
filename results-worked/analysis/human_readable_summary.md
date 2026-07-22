# Benchmark Results Summary

### Ranking by success rate

1. **A*** — 0.400
2. **Dynamic SMA*-Collapse** — 0.400
3. **ILBFS** — 0.400
4. **SMA* (memory=20%)** — 0.000
5. **SMA* (memory=30%)** — 0.000
6. **SMA* (memory=40%)** — 0.000

### Ranking by average runtime (solved instances)

1. **A*** — 4.119
2. **ILBFS** — 6.926
3. **Dynamic SMA*-Collapse** — 107.785

### Ranking by average peak memory

1. **ILBFS** — 2309.991
2. **A*** — 3168.477
3. **Dynamic SMA*-Collapse** — 4247.855
4. **SMA* (memory=20%)** — 4476.506
5. **SMA* (memory=30%)** — 4912.876
6. **SMA* (memory=40%)** — 5032.509

## Per-domain observations

### n_puzzle

- **SMA* (memory=20%)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 4476.506 MB
- **SMA* (memory=30%)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 4912.876 MB
- **SMA* (memory=40%)**: success 0.0%, avg runtime (solved) n/as, avg peak memory 5032.509 MB
- **A***: success 40.0%, avg runtime (solved) 4.119s, avg peak memory 3168.477 MB
- **Dynamic SMA*-Collapse**: success 40.0%, avg runtime (solved) 107.785s, avg peak memory 4247.855 MB
- **ILBFS**: success 40.0%, avg runtime (solved) 6.926s, avg peak memory 2309.991 MB

## Did A* fail on hard Sokoban instances?

_No hard Sokoban A* runs found in this dataset._

## Did Dynamic SMA*-Collapse improve over fixed SMA*?

Dynamic SMA*-Collapse: success 40.0%, avg runtime (solved) 107.785s, avg peak memory 4247.855 MB.
_No fixed SMA* runs found in this dataset._

## Collapse and restore behavior

Algorithms that collapsed nodes (most to least):
- **SMA* (memory=20%)**: 11645205 collapsed, 0 restored.
- **SMA* (memory=30%)**: 9967805 collapsed, 0 restored.
- **SMA* (memory=40%)**: 9410581 collapsed, 0 restored.
- **Dynamic SMA*-Collapse**: 7565574 collapsed, 5942992 restored.

Dynamic SMA*-Collapse restored 5942992 node(s) out of 7565574 collapsed (78.6% restore/collapse ratio). "Restored" means a node whose entire subtree had been collapsed away was re-expanded because it became the best leaf again -- see the `nodes_restored` docs in `algorithms/dynamic_sma_collapse.py` for exactly what this simplified SMA* counts as a restore.

Runs with at least one restore: avg runtime 2058.784s (n=2); runs with no restores: avg runtime 158.249s (n=3).

- **Memory vs. collapse/restore tradeoff**: a smaller RAM bound forces more collapsing (and, later, potentially more restoring) as previously-forgotten subtrees become competitive again and must be regenerated from scratch -- trading peak memory for extra re-expansion work. Compare the peak-memory ranking above against the collapse/restore counts here.

## Did Two-Level Dynamic SMA* improve over Dynamic SMA*-Collapse?

Two-Level Dynamic SMA*: success n/a, avg runtime (solved) n/as, avg peak memory n/a MB, nodes spilled to disk: 0, nodes loaded from disk: 0.  
Dynamic SMA*-Collapse: success 40.0%, avg runtime (solved) 107.785s, avg peak memory 4247.855 MB.

## Tradeoff discussion

- **Runtime**: see runtime ranking above; Two-Level Dynamic SMA* pays extra overhead for SQLite I/O (avg disk I/O time across all algorithms: 0.000s).
- **RAM usage**: see peak-memory ranking above; fixed and dynamic SMA* variants cap resident nodes, trading memory for potential extra runtime/collapses.
- **Disk usage**: total nodes spilled to disk across all runs: 0; total nodes loaded back: 0.
- **Collapses**: total nodes collapsed across all runs: 38589165; total nodes restored: 5942992.
- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): 0.000.

## Conclusion

- **Strongest overall (by success rate)**: A*.
- **Strongest under memory pressure (by avg peak memory)**: ILBFS.
- **Did disk spilling help?** No evidence of disk loads contributing in this run.
- **Did adaptive RAM sizing help?** RAM capacity was adjusted at least once across the dynamic algorithms.
