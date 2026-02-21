"""SQLite-based mirror health history for tracking latency over time."""

import sqlite3
import os
from datetime import datetime
from typing import Optional

from .models import PingResult


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history.db")


def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a connection and ensure tables exist."""
    conn = sqlite3.connect(db_path)
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
    """Save ping results to history DB. Returns number of rows inserted."""
    conn = _get_conn(db_path)
    ts = datetime.now().isoformat()
    rows = []
    for r in results:
        rows.append((
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
            r.ws_latency_ms,
            r.bet_latency_ms,
            r.best_latency_ms,
            int(r.ssl_valid),
            r.http_status,
            r.error,
        ))
    conn.executemany("""
        INSERT INTO ping_history
        (timestamp, domain, url, is_up, ip_address, server_location,
         dns_ms, tcp_ms, https_ms, api_ms, ws_ms, bet_ms, best_ms,
         ssl_valid, http_status, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    count = len(rows)
    conn.close()
    return count


def get_domain_history(
    domain: str,
    limit: int = 100,
    db_path: str = DB_PATH,
) -> list[dict]:
    """Get recent history for a specific mirror domain."""
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM ping_history
        WHERE domain = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (domain, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_scan(db_path: str = DB_PATH) -> list[dict]:
    """Get the most recent scan results (all mirrors from the last timestamp)."""
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    latest_ts = conn.execute(
        "SELECT MAX(timestamp) as ts FROM ping_history"
    ).fetchone()["ts"]
    if not latest_ts:
        conn.close()
        return []
    rows = conn.execute("""
        SELECT * FROM ping_history
        WHERE timestamp = ?
        ORDER BY best_ms ASC
    """, (latest_ts,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_uptime_stats(
    domain: Optional[str] = None,
    hours: int = 24,
    db_path: str = DB_PATH,
) -> dict:
    """Get uptime percentage and average latency stats."""
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
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

    rows = conn.execute(query, params).fetchall()
    conn.close()

    stats = {}
    for r in rows:
        d = dict(r)
        d["uptime_pct"] = round(d["up_checks"] / d["total_checks"] * 100, 1) if d["total_checks"] else 0
        stats[d["domain"]] = d
    return stats


def get_scan_count(db_path: str = DB_PATH) -> int:
    """Get total number of distinct scans in history."""
    conn = _get_conn(db_path)
    count = conn.execute(
        "SELECT COUNT(DISTINCT timestamp) as cnt FROM ping_history"
    ).fetchone()[0]
    conn.close()
    return count
