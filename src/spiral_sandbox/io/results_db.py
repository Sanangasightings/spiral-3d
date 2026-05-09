"""SQLite results store. One row per (scene, density, method, metric)."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  REAL NOT NULL,
    config_path TEXT,
    git_sha     TEXT,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    INTEGER NOT NULL,
    scene     TEXT NOT NULL,
    density   TEXT NOT NULL,
    method    TEXT NOT NULL,
    metric    TEXT NOT NULL,
    value     REAL,
    extra     TEXT,
    UNIQUE (run_id, scene, density, method, metric)
);

CREATE INDEX IF NOT EXISTS idx_metrics_lookup
    ON metrics (scene, density, method, metric);

CREATE TABLE IF NOT EXISTS reconstructions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL,
    scene         TEXT NOT NULL,
    density       TEXT NOT NULL,
    method        TEXT NOT NULL,
    artifact_dir  TEXT NOT NULL,
    metadata      TEXT,
    UNIQUE (run_id, scene, density, method)
);
"""


@dataclass
class MetricRow:
    scene: str
    density: str
    method: str
    metric: str
    value: Optional[float]
    extra: Optional[dict[str, Any]] = None


class ResultsDB:
    """Thin wrapper around a SQLite results store. The file path comes
    from `RunConfig.output.results_db` and is the same artifact the
    Datasette-Lite mobile viewer reads (see decisions/0001-hosting-stack)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def begin_run(
        self,
        config_path: Optional[Path] = None,
        git_sha: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO runs (started_at, config_path, git_sha, notes)"
                " VALUES (?, ?, ?, ?)",
                (time.time(), str(config_path) if config_path else None,
                 git_sha, notes),
            )
            return int(cur.lastrowid)

    def write_metric(self, run_id: int, row: MetricRow) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metrics"
                " (run_id, scene, density, method, metric, value, extra)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    row.scene,
                    row.density,
                    row.method,
                    row.metric,
                    row.value,
                    json.dumps(row.extra) if row.extra else None,
                ),
            )

    def write_reconstruction(
        self,
        run_id: int,
        scene: str,
        density: str,
        method: str,
        artifact_dir: Path,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reconstructions"
                " (run_id, scene, density, method, artifact_dir, metadata)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    scene,
                    density,
                    method,
                    str(artifact_dir),
                    json.dumps(metadata) if metadata else None,
                ),
            )

    def query_metric(
        self, scene: str, density: str, method: str, metric: str
    ) -> Optional[float]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT value FROM metrics"
                " WHERE scene=? AND density=? AND method=? AND metric=?"
                " ORDER BY id DESC LIMIT 1",
                (scene, density, method, metric),
            )
            row = cur.fetchone()
            return float(row[0]) if row and row[0] is not None else None
