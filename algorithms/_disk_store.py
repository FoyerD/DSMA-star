"""SQLite-backed disk frontier for Two-Level Dynamic SMA*.

This is an experimental, research-grade disk layer: states are serialized
with `json.dumps` (tuples round-trip as JSON arrays; `_deep_tuple` converts
them back to nested tuples on load, which matches the tuple-based state
representation used by both bundled domains generically, with no
domain-specific code needed here).

The store tracks its own read/write counts and cumulative I/O time so
callers can report `disk_read_count`, `disk_write_count`, and
`disk_io_time_seconds` without re-instrumenting every call site.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


def _deep_tuple(obj: Any) -> Any:
    if isinstance(obj, list):
        return tuple(_deep_tuple(x) for x in obj)
    return obj


@dataclass(slots=True)
class DiskNodeRecord:
    node_id: int
    parent_id: Optional[int]
    state: Any
    action: Any
    g: float
    h: float
    f: float
    depth: int


class DiskNodeStore:
    """SQLite-backed table of delayed (spilled) frontier nodes."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS disk_nodes (
                node_id INTEGER PRIMARY KEY,
                parent_id INTEGER,
                state_json TEXT NOT NULL,
                action_json TEXT,
                g REAL NOT NULL,
                h REAL NOT NULL,
                f REAL NOT NULL,
                depth INTEGER NOT NULL,
                priority_f REAL NOT NULL,
                priority_neg_g REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_disk_nodes_priority ON disk_nodes(priority_f ASC, priority_neg_g ASC)"
        )
        self._conn.commit()

        self.read_count = 0
        self.write_count = 0
        self.io_time_seconds = 0.0
        self.peak_nodes = 0

    def insert_nodes(self, records: List[DiskNodeRecord]) -> None:
        if not records:
            return
        start = time.perf_counter()
        rows = [
            (
                r.node_id,
                r.parent_id,
                json.dumps(r.state),
                json.dumps(r.action),
                r.g,
                r.h,
                r.f,
                r.depth,
                r.f,
                -r.g,
            )
            for r in records
        ]
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO disk_nodes
                (node_id, parent_id, state_json, action_json, g, h, f, depth, priority_f, priority_neg_g)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        self.io_time_seconds += time.perf_counter() - start
        self.write_count += len(records)
        self.peak_nodes = max(self.peak_nodes, self.count())

    def peek_best(self) -> Optional[DiskNodeRecord]:
        start = time.perf_counter()
        cur = self._conn.execute(
            "SELECT node_id, parent_id, state_json, action_json, g, h, f, depth "
            "FROM disk_nodes ORDER BY priority_f ASC, priority_neg_g ASC LIMIT 1"
        )
        row = cur.fetchone()
        self.io_time_seconds += time.perf_counter() - start
        return self._row_to_record(row) if row else None

    def pop_best_batch(self, k: int) -> List[DiskNodeRecord]:
        return self._pop_batch(order_sql="priority_f ASC, priority_neg_g ASC", k=k)

    def pop_worst_batch(self, k: int) -> List[DiskNodeRecord]:
        return self._pop_batch(order_sql="priority_f DESC, priority_neg_g DESC", k=k)

    def _pop_batch(self, order_sql: str, k: int) -> List[DiskNodeRecord]:
        if k <= 0:
            return []
        start = time.perf_counter()
        cur = self._conn.execute(
            f"SELECT node_id, parent_id, state_json, action_json, g, h, f, depth "
            f"FROM disk_nodes ORDER BY {order_sql} LIMIT ?",
            (k,),
        )
        rows = cur.fetchall()
        if rows:
            ids = [row[0] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            self._conn.execute(f"DELETE FROM disk_nodes WHERE node_id IN ({placeholders})", ids)
            self._conn.commit()
        self.io_time_seconds += time.perf_counter() - start
        self.read_count += len(rows)
        return [self._row_to_record(row) for row in rows]

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM disk_nodes")
        return cur.fetchone()[0]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM disk_nodes")
        self._conn.commit()

    def close(self, delete_file: bool = True) -> None:
        self._conn.close()
        if delete_file:
            try:
                self.db_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _row_to_record(row) -> DiskNodeRecord:
        node_id, parent_id, state_json, action_json, g, h, f, depth = row
        return DiskNodeRecord(
            node_id=node_id,
            parent_id=parent_id,
            state=_deep_tuple(json.loads(state_json)),
            action=json.loads(action_json) if action_json is not None else None,
            g=g,
            h=h,
            f=f,
            depth=depth,
        )
