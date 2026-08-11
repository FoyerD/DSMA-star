Technical Implementation Guide: Iterative Linear Best-First Search (ILBFS)

1. Introduction and Algorithmic Context

Iterative Linear Best-First Search (ILBFS) is a linear-space variant of Best-First Search (BFS) that operates iteratively using an OPEN list and expansion cycles. It is functionally identical to Recursive Best-First Search (RBFS); both algorithms visit the exact same nodes in the exact same order. However, ILBFS replaces the complex recursive backtracking of RBFS with an iterative framework utilizing two primary macro operators: Collapse and Restore.

Pedagogical and Engineering Motivation

While RBFS is often difficult for practitioners to implement and debug due to its virtual bounds and recursive stack, ILBFS uses the familiar structure of a standard BFS. It is designed to bridge the gap between memory-intensive algorithms like A^* and linear-space algorithms like IDA^*, providing a clearer implementation path for developers requiring best-first expansion orders without exponential memory growth.

Comparison with Standard BFS

* Memory Usage: Standard BFS stores the full search tree, requiring O(b^d) space. ILBFS maintains only the "Principal Branch" and its immediate siblings, reducing space complexity to O(b \times d) (or O(d) if the branching factor b is constant).
* Structural Constraint: ILBFS strictly adheres to a Principal Branch Invariant, eagerly pruning subtrees that are no longer on the most promising path to the goal.

2. Core Concepts and Definitions

Value Types

Effective search management in ILBFS relies on two distinct cost metrics:

* Static Value (f(n)): The standard cost estimate, defined as f(n) = g(n) + h(n).
* Stored Value (F(n)): The minimal f(n) of the frontier nodes within a subtree that has been collapsed into node n. Initially, F(n) = f(n).

Key Invariants

* Principal Branch Invariant: Memory only contains the internal nodes on the path from the root to the current best node, plus the immediate children of those internal nodes.
* Perimeter Invariant: The OPEN list always represents a complete "cut" or perimeter of the search tree. This ensures that at any point before termination, a node on the path to the goal is present in OPEN.

Fundamental Operators

* Collapse Macro: Triggered during branch shifts. It deletes a subtree from memory and backs up the best frontier value (F(n)) into its root.
* Restore Macro: The inverse of collapse. It lazily restores a previously pruned subtree's structure during expansion by propagating stored F-values down to generated children.

3. Data Structures and Node Architecture

Primary Structures

* OPEN List: A priority queue containing the current frontier nodes of the search, ordered by their stored F(n) values.
* TREE: A pointer-based structure representing the current principal branch and its children.

Node Object Requirements

Each node object must implement the following fields:

* Static Value (f(n)): The fixed g+h calculation.
* Stored Value (F(n)): Initialized to f(n); updated during collapse and restore operations.
* Parent Pointer: Essential for the bottom-up traversal during the Collapse phase.
* List of Children: Maintained for internal nodes currently within the TREE structure.

4. The Iterative Logic: Main Search Loop

The search process is a cycle that alternates between deepening the current branch and shifting to more promising branches.

1. Initialization:
  * Insert the Root node R into OPEN and TREE.
  * Set oldbest = NULL.
2. Extraction: Extract the node with the minimal F(n) from OPEN; designate this as best.
3. Goal Check: If best is the goal, terminate.
4. Invariance Maintenance (Case 1 vs. Case 2):
  * Case 1 (Deepening): If oldbest is the parent of best, the search is deepening. Skip the Collapse phase.
  * Case 2 (Branch Shift): If oldbest is not the parent of best (and oldbest \neq NULL), trigger the Collapse Phase.
5. Expansion and Restore:
  * Perform the Restore/Expansion Phase on best.
6. Cycle Completion: Set oldbest = best and return to step 2.

Pseudocode:

```
Input: Root R
Insert R into OPEN and TREE
oldbest = NULL
while OPEN not empty do {
    best = extract min(OPEN)
    if goal(best) then exit
    while (oldbest != best.parent) do {
        oldbest.val <- min(values of oldbest children)
        Insert oldbest to OPEN
        Delete all children of oldbest from OPEN and TREE
        oldbest <- oldbest.parent
    }
    foreach child C of best do {
        F(C) <- f(C)
        if F(best) > f(best) and F(best) > F(C) then
            F(C) <- F(best)
        Insert C to OPEN and TREE
    }
    oldbest <- best
}
```

5. Phase 1: The Bottom-Up Collapse Macro

When the search shifts to a node best that is not a child of the previous oldbest, the algorithm must prune the previous branch to maintain linear space.

Implementation Instructions:

1. Iterative Pruning: Starting from oldbest, traverse upward toward the root.
2. Loop Logic: While oldbest \neq best.parent:
  * Update oldbest.F = \min(F\text{-values of } oldbest\text{'s children}).
  * Re-insert oldbest into the OPEN list.
  * Delete all children of oldbest from both the OPEN list and the TREE structure to free memory.
  * Move the pointer upward: oldbest = oldbest.parent.
3. Termination: The loop stops precisely when it reaches the common ancestor A (best.parent). This ensures that node B (the sibling of best and ancestor of the previous oldbest) is collapsed, while the path to best remains intact.

6. Phase 2: Restore Propagation and Expansion

If a selected best node was previously a collapsed root, the algorithm must reveal its subtree. This expansion is logically a Depth-First Search (DFS) bounded by F(best).

Restore Propagation Rule (Pathmax)

When expanding best:

1. Generate all children C of best.
2. For each child C, initialize F(C) = f(C).
3. Apply Propagation: If F(best) > f(best) and F(best) > F(C), update F(C) = F(best).
4. Insert the updated children into the OPEN list and the TREE structure.

This rule mimics the "pathmax" method, passing the backed-up cost down the tree. It allows the search to "restore" the old frontier without a separate recursive pass. The search will naturally deepen along this branch in subsequent cycles until it reaches a node where f(n) = F(best), which represents the previous search frontier.

7. Practical Implementation and Complexity Notes

Memory Efficiency

ILBFS maintains a space complexity of O(b \times d). Because the algorithm only keeps the siblings of the nodes on the path to best, the total number of nodes in memory is restricted to the branching factor times the maximum depth.

Collapsed Root Detection (Observation 2)

Implementers must not use binary flags to identify collapsed roots. Per Observation 2, a node n is a collapsed root if and only if F(n) > f(n). If F(n) = f(n), the node is an unexpanded frontier node.

Robustness to Non-Monotonic Costs

Unlike IDA^*, which may suffer from excessive backtracking when f(n) decreases along a path, ILBFS is robust against non-monotonic costs. The Restore Propagation Rule ensures that F(n) values never decrease, preventing the algorithm from re-exploring subtrees that have already been proven to have minimal costs higher than the current bound.

Runtime Performance

* OPEN List Operations: Given that the OPEN list size is O(b \times d), operations take O(\log d) time, which is negligible compared to node expansion.
* Node Visitations: Total runtime is comparable to RBFS. While node regeneration (re-expansion) occurs, it is the necessary trade-off for linear space.

8. Implementation Notes: Heap Tie-Breaking

Critical implementation detail: when multiple nodes in OPEN share the same F
value, the heap tie-breaking order determines whether the algorithm oscillates
or converges.

The Problem

After a collapse backs up F values, a sibling node and the current branch's
children often end up with identical F values. The heap pops whichever node has
the lower tie-breaker value. If that node is a sibling (not a child of
oldbest), popping it triggers a collapse that deletes the just-expanded
children. The collapsed node is then re-pushed with the same F value as the
sibling's children, producing an infinite oscillation loop:

    sibling(F=10) popped → collapse deletes children → re-expand sibling →
    children(F=10) pushed → sibling(F=10) popped again → ...

The Fix: Collapse-Count Tie-Breaking

Pure depth-first (``-depth``) works on shallow instances but oscillates on
deep ones (e.g., depth-28 15-puzzle). Pure shallower-first (``depth``) works
on deep instances but oscillates on shallow ones (e.g., depth-24). The root
cause is that a collapsed node gets re-pushed with the same F, and a static
tiebreaker always picks the same winner.

The solution combines depth-first expansion with a per-node oscillation penalty:

    heap entry = (F + collapse_count, -depth, state_key)

- ``-depth`` (negated depth): deeper nodes win ties — allows the search to
  deepen along the current branch, which is efficient for moderate depths.
- ``collapse_count``: incremented each time a node's children are deleted by
  the Collapse macro.  Every collapse makes the node's effective priority
  worse by 1.  After enough collapses, the node loses the tie to siblings,
  forcing the search to explore a different branch.  This breaks the infinite
  re-expansion loop.

The ``collapse_count`` field lives on ``_Node`` (an integer, default 0).
During heap rebuild after collapse, all live nodes use their current
``(F + collapse_count, -depth, state_key)``.

Performance: on the depth-24 15-puzzle instance, 3390 expansions, 0.36s
(previously 2964 expansions with pure ``-depth``, but that approach failed on
depth-28). On the depth-28 instance, 182K expansions, 14s (previously
oscillated infinitely). The penalty adds ~14% overhead on depth-24 compared to
pure ``-depth`` but makes depth-28 tractable.

Note: the pseudocode in this document does not specify tie-breaking because it
is an implementation detail. However, the choice is consequential: preferring
shallower nodes (siblings) causes collapse oscillation; preferring deeper
nodes (children of the current branch) allows the search to deepen correctly.
The collapse_count penalty ensures neither choice leads to infinite loops.

Heap entries use ``(F + collapse_count, -depth, state_key)`` where
``state_key`` is the hashable state identifier (not a ``_Node`` reference).
When a node is popped, its ``_Node`` is looked up from the ``nodes`` dict;
stale entries (deleted from ``nodes`` or whose F value was updated by collapse)
are detected and skipped.  Storing state_keys instead of _Node references
allows collapsed nodes to be garbage collected immediately, preventing the
memory leak that would otherwise occur from stale heap entries keeping _Node
objects (and their parent chains) alive.

Heap Purge on Collapse

Pseudocode line 79 says "Delete all children of oldbest from OPEN and TREE".
Deleting from TREE (the ``nodes`` dict) is straightforward; deleting from
OPEN (the heap) requires removing stale entries.  Our implementation rebuilds
the heap from the live ``nodes`` dict after each collapse loop — an
O(b * d) pass that purges all stale entries in one shot.  Two alternatives
from the literature (Heapify vs Sift-Down) showed near-identical performance
in Grabovski & Yasur (2024).

Before this fix, the heap grew monotonically to millions of entries because
collapsed children's heap entries were never removed — only skipped at pop
time.  On a depth-41 Korf instance this caused 5M heap entries consuming
~3.3 GB, versus A*'s 134K entries at 276 MB.

9. Summary of Macro-Based BFS Continuum

The following table contextualizes ILBFS within the spectrum of Best-First Search algorithms.

Dimension	BFS	SMA*	ILBFS
Memory Usage	Exponential (O(b^d))	Bounded (M)	Linear (O(b \times d))
Collapse Frequency	None	Lazy (when memory M is full)	Eager (at every branch shift)
Key Structural Invariant	Full Search Tree	Available Memory Bound	Principal Branch Invariant
Expansion Order	Best-First	Best-First	Best-First (identical to RBFS)

10. Validation and Practical Findings

The following summarizes findings from Grabovski & Yasur (2024), "Validation
and Implementation of ILBFS" (arXiv:2407.01637v1), which provides the first
peer-reviewed practical implementation and empirical validation of ILBFS.

10.1 Testing Domain

The original paper validated ILBFS on the 8-puzzle (3x3) with randomly
generated instances at solution depths 1--14.  For larger benchmarks in this
project we recommend using easier instances of the 15-puzzle (4x4) — for
example scramble depths 10--20 or Korf instances at optimal depths ≤ 35 —
rather than treating the 8-puzzle as the definitive test domain.  The 8-puzzle
has a branching factor of ~2.67 and a maximum depth of 31, which is too small
to expose the heap-management and memory-scaling issues that arise at depth
40+ on the 15-puzzle.

10.2 Critical Implementation Requirements

The paper confirms that a naive implementation following only the pseudocode
fails in practice.  Two extensions are essential:

Tie-Breaking (Section 8):  Without deterministic tie-breaking, ILBFS
    oscillates between competing subtrees, producing infinite loops.  The
    paper uses creation-time ordering (depth-first preference); our
    implementation achieves the same effect with a negated monotonic order
    counter in the heap tuple.

Explicit Node Deletion from OPEN:  The collapse macro must remove
    children from both the TREE structure and the OPEN list (pseudocode
    line 79).  Failing to purge OPEN causes the heap to grow
    monotonically with total nodes generated rather than staying
    O(b * d).  Two deletion strategies were evaluated:

    * Heapify method: remove entries from the heap array and rebuild
      with heapq.heapify — O(n) per collapse, where n = O(b * d).
    * Sift-down method: replace deleted entries with the last heap
      element and sift — O(log n) per individual deletion.

    Both strategies showed near-identical performance in the paper's
    benchmarks.  Our implementation uses the Heapify method: after the
    collapse loop completes, the heap is rebuilt from the live `nodes`
    dict in a single O(b * d) pass.

10.3 Empirical Results (from the paper)

1. Expansion order equivalence: with proper tie-breaking, ILBFS expands
   nodes in exact equivalence to RBFS.
2. Runtime overhead: ILBFS runs ~3x slower than RBFS due to heap
   management overhead (deletion, rebuilding).  The Heapify and
   Sift-down variants performed nearly identically.
3. Linear memory: both ILBFS and RBFS solved all test instances within
   linear memory, validating the theoretical O(b * d) guarantee.

10.4 Implications for the 15-puzzle

On the 15-puzzle, ILBFS re-expands nodes far more than A* (which has a
closed set) because collapsed subtrees are regenerated from scratch on
re-expansion.  At scramble depths 40+ this leads to node counts 20--60x
higher than A*, with correspondingly higher runtime.  This is the
inherent cost of O(b * d) memory — not a bug — but it means ILBFS is
not competitive with A* on very hard instances.  For practical
comparison, use 15-puzzle instances at scramble depths 10--25 or Korf
instances at optimal depths ≤ 35.

