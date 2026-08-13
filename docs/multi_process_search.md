# Multi-Process Search: A New Algorithm Design

> **SUPERSEDED** — this is an early, coarser design proposal. The current,
> agreed design for the next algorithm is **`docs/mp_rbfs.md`** (Multi-Path
> RBFS). The key changes: single-threaded *proc* abstraction (not OS
> processes), a pluggable scheduler with per-expansion quantum, a shared
> global tree (transposition table) instead of per-process memory budgets,
> no proc spawning/backtracking, and suboptimal solutions accepted by design.
> Read `docs/mp_rbfs.md` first; this document is kept for historical context
> and for the parts that survived (A* builds the initial frontier, one search
> per frontier node, scheduling policies).

## Project Context

This is a research project (`DSMA-star`) comparing heuristic search algorithms on the 15-puzzle domain. The goal is to find optimal solutions under memory constraints. We currently have two algorithms:

- **A\*** — Standard graph-search A\* with a binary heap. Optimal when h is admissible. Uses unlimited memory (all generated nodes kept in RAM). Fails when the search tree exceeds available RAM.

- **RBFS** — Recursive Best-First Search. Uses the recursion stack to maintain O(b*d) memory. Visits the same nodes as A\* in best-first order but with linear memory. Faster than ILBFS due to no heap management overhead.

### Test domain

- **15-puzzle** (4x4 sliding tile): Manhattan distance heuristic (admissible). States are tuples of 16 ints. 4 successors per state (up/down/left/right).

### Key design decisions

- **No wall-clock timeout.** A stopwatch structurally favors A\* (no memory-management overhead). Runs stop only on: solution found, RSS > max-memory-mb, or max-nodes safety valve (5M default).
- **Memory ceiling enforced via `psutil`** sampled every 256 limit-checks. Not continuous — a single large alloc between samples could briefly exceed it.
- **RBFS** = Recursive Best-First Search. O(b*d) memory via the recursion stack. No stack exhaustion risk with appropriate recursion limit.

### Current benchmark metrics

Per run: `success`, `solution_cost`, `runtime_seconds`, `peak_memory_mb`, `nodes_expanded`, `nodes_generated`, `max_frontier_size`, `reexpansions`.

---

## The Problem

Our two current algorithms represent opposite ends of the memory-performance spectrum:

- **A\*** keeps every generated node in RAM. It fails when the search tree exceeds available RAM. For hard 15-puzzle instances (scramble depth 40+), A\* may exhaust memory before finding a solution.

- **RBFS** uses O(b*d) memory via the recursion stack. It never runs out of memory (with a raised recursion limit), but it re-expands on hard instances. This makes it slow on deep instances, but much faster than ILBFS.

**The core limitation**: a single-tree search must choose between keeping the full frontier (A\*) or collapsing it eagerly (RBFS). There is no middle ground — no way to explore multiple promising subtrees simultaneously while staying within a global memory budget.

---

## The New Idea: Multi-Process Search

### Key Insight

Instead of one search tree, run **multiple independent searches in parallel**, each rooted at a different leaf node. Treat each search as a "process" with its own memory budget, and use OS-style scheduling to decide which process runs next.

### Algorithm Flow

```
Phase 1: A* (the "fork")
  Run A* until the frontier has N leaf nodes.
  These N leaves become the roots of N independent searches.

Phase 2: RBFS Processes (the "schedulers")
  Each leaf spawns a SearchProcess running RBFS from that leaf.
  A scheduler decides which process runs next.
  Each process runs RBFS (recursive Collapse/Restore) from its root.
  Results update a shared transposition table.

Phase 3: Solution
  When any process finds a goal, reconstruct the full path:
  A* path to leaf + RBFS path from leaf to goal.
```

### Why this works

1. **No redundant expansion**: Each RBFS process starts from a leaf, not the problem root. It only explores its own subtree. No duplication across processes (unless they encounter the same state, handled by the shared transposition table).

2. **Memory isolation**: Each process has its own memory budget. One process can't starve others.

3. **Natural parallelism model**: Processes are independent. Scheduling is the only coordination point.

4. **A\* does the heavy lifting**: A\* efficiently builds the initial frontier (the "easy" part of the search). RBFS handles the deep subtrees (the "hard" part).

### Visual

```
A* (root -> leaves)              RBFS processes (leaves -> goal)
        |                                |
        v                                v
   +---------+                  +------------------+
   |  root   |                  |  leaf1 -> ... -> ?|
   |  / \    |                  |  leaf2 -> ... -> ?|
   | leaf1   |  ============>   |  leaf3 -> ... -> ?|
   | leaf2   |  (N processes    |  ...              |
   | leaf3   |   from leaves)   |  leafN -> ... -> ?|
   +---------+                  +------------------+
```

Each RBFS process:
- Uses recursive search (no heap management overhead)
- Only explores nodes reachable from its leaf
- Reports back: solution found, or bound exceeded (no solution in this subtree)

---

## Architecture

### Core Components

#### 1. SearchProcess

```python
@dataclass
class SearchProcess:
    process_id: int
    root_state: Any          # leaf node from A*
    root_g: float            # g-value at the leaf
    parent_key: Any          # for solution reconstruction (A* parent)
    bound: float             # current RBFS f-value bound
    iteration: int           # current iteration number
    memory_budget: int       # max nodes this process can keep
    nodes_expanded: int      # counter
    status: str              # "ready" | "running" | "preempted" | "solved" | "exhausted"
    solution: Optional[SearchResult]
```

#### 2. ProcessTable

```python
class ProcessTable:
    processes: List[SearchProcess]
    transposition_table: Dict  # shared across all processes (state -> best g)
    solution: Optional[SearchResult]  # best found so far
```

#### 3. Scheduler (abstract)

```python
class Scheduler(ABC):
    @abstractmethod
    def select_next(self, table: ProcessTable) -> SearchProcess: ...
```

#### 4. MemoryAllocator

```python
class MemoryAllocator:
    def allocate(self, total_memory: int, processes: List[SearchProcess]) -> Dict[int, int]:
        """Returns {process_id: memory_budget}"""
```

---

## Scheduling Policies

| Policy | Selection Rule | Memory Allocation | Optimality |
|--------|---------------|-------------------|------------|
| **Priority** | Always lowest f-value first | Equal shares | Optimal (like A\*) |
| **Round-Robin** | Fixed time slice (1 iteration per process) | Equal shares | May not be optimal |
| **Proportional** | Lowest f-value first | Memory proportional to 1/f | Likely optimal |
| **Lottery** | Random draw (tickets proportional to 1/f) | Equal shares | Probabilistic |

### Time Slice

For round-robin, the time slice is **1 RBFS call**. Each call explores a subtree from the process root using recursive best-first search.

### Memory Allocation

- **Equal shares**: `total_memory / num_processes` per process.
- **Proportional**: `total_memory * (1/f_i) / sum(1/f_j for all j)` — lower f gets more memory.
- **Dynamic**: Could be extended to adjust based on collapse ratio.

---

## Design Decisions

### Shared Transposition Table

All processes share one transposition table (state -> best g-value seen). This:
- Avoids duplicate work when two processes encounter the same state
- Requires no coordination (processes just read/write to the table)
- May cause a process to skip a state that another process is currently exploring (acceptable — the other process will find the better path)

### Batch Creation

All N processes are created at once from the A\* frontier. No dynamic spawning. This simplifies the scheduler and process table.

### Solution Reconstruction

When a process finds a solution:
1. The process has the path from its leaf to the goal (from RBFS).
2. Prepend the A\* path from root to leaf.
3. Return the full path.

This requires storing the A\* parent pointer for each leaf (the `parent_key` field in SearchProcess).

### RBFS Subtree Root

RBFS accepts a `root_state` and `root_g` parameter:
- Starts from `root_state` (not `problem.initial_state`)
- Initial bound = `root_g + h(root_state)`
- Recursive search loop from `root_state` with current bound
- Returns path from `root_state` to goal (or bound exceeded)

---

## Comparison to Existing Algorithms

| Aspect | A\* | RBFS | Multi-Process |
|--------|-----|-------|---------------|
| Search structure | Single tree | Single tree | N independent subtrees |
| Memory management | Keep everything | Recursion stack (O(b*d)) | Per-process budget |
| Parallelism | None | None | Natural (processes) |
| Optimality | Guaranteed (admissible h) | Guaranteed (identical to RBFS) | Depends on scheduler |
| When it fails | RAM exhausted | Re-expands exponentially | All processes exhausted |

### When Multi-Process shines

1. **Multiple promising paths**: When the search tree has many branches worth exploring, A\*/RBFS commit to one. Multi-process explores N simultaneously.

2. **Memory-constrained**: Each process gets a small budget, but collectively they cover more ground than a single RBFS with the same total budget.

3. **Heterogeneous difficulty**: Some subtrees are easy (short solution), others are hard (deep). Processes can be scheduled to tackle easy ones first (priority scheduler).

4. **Scheduling flexibility**: Different policies optimize for different goals (optimality, speed, coverage).

---

## Open Questions

1. **Optimality guarantee**: With priority scheduling (always lowest f first), is the algorithm guaranteed to find the optimal solution? (Likely yes, since it mimics A\*'s expansion order.)

2. **Process count N**: How many leaves should become processes? Fixed count (e.g., 100)? Proportional to depth? Until memory fills?

3. **RBFS iteration cost**: Each call explores a subtree recursively. For deep subtrees, this could be expensive. Should we limit the number of nodes expanded per process?

4. **Transposition table size**: The shared table grows with total nodes generated across all processes. Should it have a size limit? (Unlike the per-process memory budgets, the table is shared.)

5. **Dynamic process creation**: Should new processes spawn when old ones finish? Or is batch creation sufficient?

6. **Collapse behavior in subtree RBFS**: When running RBFS from a leaf subtree root, the recursion naturally explores the subtree. The shared transposition table prevents redundant work across processes.

---

## Implementation Plan

### Phase 1: Core Data Structures

Create `algorithms/multi_process.py`:
- `SearchProcess` dataclass
- `ProcessTable` class (manages active processes, shared transposition table)
- `MemoryAllocator` (equal, proportional)

### Phase 2: Modify RBFS for Subtree Search

Modify `algorithms/rbfs.py`:
- Add `root_state` and `root_g` parameters to `search()`
- RBFS starts from `root_state` instead of `problem.initial_state`
- Each call: recursive search from `root_state` with current bound
- Returns `SearchResult` with path from `root_state` to goal

### Phase 3: Scheduler Implementations

Create scheduler classes:
- `PriorityScheduler` — always lowest f-value first (optimal)
- `RoundRobinScheduler` — fixed time slice, cycle through processes
- `ProportionalScheduler` — memory proportional to 1/f
- `LotteryScheduler` — random draw with tickets proportional to 1/f

### Phase 4: Main Algorithm Class

Create `MultiProcessSearch(SearchAlgorithm)`:
1. Run A\* until frontier has N nodes (the "leaves")
2. Create processes from leaves (batch creation)
3. Loop:
   a. Scheduler picks next process
   b. Process runs RBFS for 1 iteration from its root
   c. Results update shared transposition table
   d. If solution found: reconstruct path, return
   e. Process preempted, saved to process table
4. Return best solution or failure

### Phase 5: CLI Integration

Add flags:
- `--scheduler {priority,round-robin,proportional,lottery}`
- `--num-processes N` (fixed count of A\* leaves -> processes)
- `--process-memory M` (per-process node budget)

### Phase 6: Tests

- Unit tests for each scheduler
- Integration test: all schedulers on trivial 8-puzzle
- Comparison test: multi-process vs single RBFS on 15-puzzle

---

## Example CLI Usage

```bash
# Run multi-process search with priority scheduling
python main.py --domain puzzle --scheduler priority --num-processes 100 --process-memory 500

# Compare all scheduling policies
python main.py --domain puzzle --scheduler priority --num-processes 100 --process-memory 500
python main.py --domain puzzle --scheduler round-robin --num-processes 100 --process-memory 500
python main.py --domain puzzle --scheduler proportional --num-processes 100 --process-memory 500
python main.py --domain puzzle --scheduler lottery --num-processes 100 --process-memory 500
```
