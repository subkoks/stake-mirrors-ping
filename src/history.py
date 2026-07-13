"""SQLite-based mirror health history for tracking latency over time."""

import os
import sqlite3
from datetime import datetime

from .models import PingResult

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history.db")


class HistoryDB:
    """Context manager for SQLite history database operations."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> "HistoryDB":
        self.conn = sqlite3.connect(self.db_path)
        self._ensure_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conn:
            self.conn.close()

    def _ensure_tables(self) -> None:
        """Create tables and indexes if they don't exist."""
        assert self.conn is not None
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                domain TEXT NOT NULL,
                url TEXT NOT NULL,
                is_up INTEGER NOT NULL,
                ip_address TEXT,
                server_location TEXT,
                dns_ms REAL,
                tcp_ms REAL,
                https_ms REAL,
                api_ms REAL,
                ws_ms REAL,
                bet_ms REAL,
                best_ms REAL,
                ssl_valid INTEGER,
                http_status INTEGER,
                error TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ping_domain_ts
            ON ping_history (domain, timestamp)
        """)
        self.conn.commit()

    def save_results(self, results: list[PingResult]) -> int:
        """Save ping results to history DB. Returns number of rows inserted."""
        assert self.conn is not None
        ts = datetime.now().isoformat()
        rows = []
        for r in results:
            rows.append(
                (
                    ts,
                    r.mirror.domain,
                    r.mirror.url,
                    int(r.is_up),
                    r.ip_address,
                    r.server_location,
                    r.dns_resolve_ms,
                    r.tcp_latency_ms,
                    r.https_latency_ms,
                    r.api_latency_ms,
                    None,  # ws_ms — deprecated
                    r.bet_latency_ms,
                    r.best_latency_ms,
                    int(r.ssl_valid),
                    r.http_status,
                    r.error,
                )
            )
        self.conn.executemany(
            """
            INSERT INTO ping_history
            (timestamp, domain, url, is_up, ip_address, server_location,
             dns_ms, tcp_ms, https_ms, api_ms, ws_ms, bet_ms, best_ms,
             ssl_valid, http_status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    def get_domain_history(self, domain: str, limit: int = 100) -> list[dict]:
        """Get recent history for a specific mirror domain."""
        assert self.conn is not None
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            """
            SELECT * FROM ping_history
            WHERE domain = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (domain, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_scans(self, limit: int = 10) -> list[dict]:
        """Get recent scan timestamps with mirror counts."""
        assert self.conn is not None
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            """
            SELECT
                timestamp,
                COUNT(*) as mirror_count,
                SUM(is_up) as up_count
            FROM ping_history
            GROUP BY timestamp
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_mirror_history(self, domain: str, days: int = 7) -> list[dict]:
        """Get history for a mirror over the last N days."""
        assert self.conn is not None
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            """
            SELECT * FROM ping_history
            WHERE domain = ?
            AND timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
        """,
            (domain, f"-{days} days"),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_scan(self) -> list[dict]:
        """Get the most recent scan results (all mirrors from the last timestamp)."""
        assert self.conn is not None
        self.conn.row_factory = sqlite3.Row
        latest_ts = self.conn.execute(
            "SELECT MAX(timestamp) as ts FROM ping_history"
        ).fetchone()["ts"]
        if not latest_ts:
            return []
        rows = self.conn.execute(
            """
            SELECT * FROM ping_history
            WHERE timestamp = ?
            ORDER BY best_ms ASC
        """,
            (latest_ts,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_uptime_stats(
        self, domain: str | None = None, hours: int = 24
    ) -> dict[str, dict]:
        """Get uptime percentage and average latency stats."""
        assert self.conn is not None
        self.conn.row_factory = sqlite3.Row
        query = """
            SELECT
                domain,
                COUNT(*) as total_checks,
                SUM(is_up) as up_checks,
                ROUND(AVG(CASE WHEN is_up THEN best_ms END), 2) as avg_best_ms,
                ROUND(MIN(CASE WHEN is_up THEN best_ms END), 2) as min_best_ms,
                ROUND(MAX(CASE WHEN is_up THEN best_ms END), 2) as max_best_ms,
                ROUND(AVG(CASE WHEN is_up THEN tcp_ms END), 2) as avg_tcp_ms,
                ROUND(AVG(CASE WHEN is_up THEN api_ms END), 2) as avg_api_ms
            FROM ping_history
            WHERE timestamp >= datetime('now', ?)
        """
        params: list = [f"-{hours} hours"]
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        query += " GROUP BY domain ORDER BY avg_best_ms ASC"

        rows = self.conn.execute(query, params).fetchall()

        stats = {}
        for r in rows:
            d = dict(r)
            d["uptime_pct"] = (
                round(d["up_checks"] / d["total_checks"] * 100, 1)
                if d["total_checks"]
                else 0
            )
            stats[d["domain"]] = d
        return stats

    def get_uptime_stats_serialized(
        self, domain: str | None = None, hours: int = 24
    ) -> list:
        """Get uptime stats as serialized schemas."""
        from .core.serializers import HistoryStatsSchema

        raw_stats = self.get_uptime_stats(domain, hours)
        return [
            HistoryStatsSchema(
                domain=domain,
                uptime_pct=data["uptime_pct"],
                total_checks=data["total_checks"],
                avg_best_ms=data["avg_best_ms"],
                min_best_ms=data["min_best_ms"],
                max_best_ms=data["max_best_ms"],
                avg_tcp_ms=data["avg_tcp_ms"],
                avg_api_ms=data["avg_api_ms"],
            )
            for domain, data in raw_stats.items()
        ]

    def get_scan_count(self) -> int:
        """Get total number of distinct scans in history."""
        assert self.conn is not None
        count: int = self.conn.execute(
            "SELECT COUNT(DISTINCT timestamp) as cnt FROM ping_history"
        ).fetchone()[0]
        return count


# Legacy functions for backward compatibility
def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a connection and ensure tables exist (legacy)."""
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            domain TEXT NOT NULL,
            url TEXT NOT NULL,
            is_up INTEGER NOT NULL,
            ip_address TEXT,
            server_location TEXT,
            dns_ms REAL,
            tcp_ms REAL,
            https_ms REAL,
            api_ms REAL,
            ws_ms REAL,
            bet_ms REAL,
            best_ms REAL,
            ssl_valid INTEGER,
            http_status INTEGER,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ping_domain_ts
        ON ping_history (domain, timestamp)
    """)
    conn.commit()
    return conn


def save_results(results: list[PingResult], db_path: str = DB_PATH) -> int:
    """Save ping results to history DB (legacy wrapper)."""
    with HistoryDB(db_path) as db:
        return db.save_results(results)


def get_domain_history(
    domain: str,
    limit: int = 100,
    db_path: str = DB_PATH,
) -> list[dict]:
    """Get recent history for a specific mirror domain (legacy wrapper)."""
    with HistoryDB(db_path) as db:
        return db.get_domain_history(domain, limit)


def get_latest_scan(db_path: str = DB_PATH) -> list[dict]:
    """Get the most recent scan results (legacy wrapper)."""
    with HistoryDB(db_path) as db:
        return db.get_latest_scan()


def get_uptime_stats(
    domain: str | None = None,
    hours: int = 24,
    db_path: str = DB_PATH,
) -> dict:
    """Get uptime percentage and average latency stats (legacy wrapper)."""
    with HistoryDB(db_path) as db:
        return db.get_uptime_stats(domain, hours)


def get_scan_count(db_path: str = DB_PATH) -> int:
    """Get total number of distinct scans in history (legacy wrapper)."""
    with HistoryDB(db_path) as db:
        return db.get_scan_count()
