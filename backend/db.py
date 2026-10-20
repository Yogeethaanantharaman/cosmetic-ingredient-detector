"""Persistence helpers for the anonymous browser-scoped scan workspace."""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import unquote, urlparse

logger = logging.getLogger("inci_sight.db")
DB_READY = False


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return None
    try:
        import mysql.connector
    except ImportError:
        logger.warning("MySQL driver is unavailable; persistent workspace is disabled.")
        return None
    parsed = urlparse(dsn)
    if parsed.scheme not in {"mysql", "mysql+mysqlconnector", "mysql+pymysql"}:
        logger.error("DATABASE_URL must use a MySQL-compatible URL scheme.")
        return None
    options = {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": unquote(parsed.path.lstrip("/")),
        "connection_timeout": 5,
        "ssl_disabled": False,
        "autocommit": False,
    }
    ca = os.getenv("DATABASE_SSL_CA")
    if ca:
        options["ssl_ca"] = ca
        options["ssl_verify_cert"] = True
        options["ssl_verify_identity"] = True
    return mysql.connector.connect(**options)


def initialize_database() -> bool:
    """Create only additive tables; never reset existing workspace data."""
    global DB_READY
    connection = None
    try:
        connection = _connect()
        if connection is None:
            DB_READY = False
            return False
        cursor = connection.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS inci_watchlists (
                client_id VARCHAR(64) NOT NULL,
                ingredient VARCHAR(128) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (client_id, ingredient)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS inci_scans (
                id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                client_id VARCHAR(64) NOT NULL,
                product_name VARCHAR(255) NOT NULL DEFAULT '',
                filename VARCHAR(255) NOT NULL DEFAULT '',
                extracted_text MEDIUMTEXT NOT NULL,
                ingredients_json MEDIUMTEXT NOT NULL,
                matches_json MEDIUMTEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX inci_scans_client_created (client_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        )
        connection.commit()
        cursor.close()
        DB_READY = True
        return True
    except Exception:
        logger.exception("Managed database unavailable; using browser-local persistence fallback.")
        DB_READY = False
        return False
    finally:
        if connection is not None:
            connection.close()


def is_ready() -> bool:
    return DB_READY


def get_watchlist(client_id: str) -> list[str] | None:
    connection = _connect()
    if connection is None:
        return None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT ingredient FROM inci_watchlists WHERE client_id=%s ORDER BY created_at, ingredient", (client_id,))
        values = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return values
    except Exception:
        logger.exception("Could not read watchlist.")
        return None
    finally:
        connection.close()


def replace_watchlist(client_id: str, ingredients: list[str]) -> bool:
    connection = _connect()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM inci_watchlists WHERE client_id=%s", (client_id,))
        if ingredients:
            cursor.executemany(
                "INSERT INTO inci_watchlists (client_id, ingredient) VALUES (%s, %s)",
                [(client_id, name) for name in ingredients],
            )
        connection.commit()
        cursor.close()
        return True
    except Exception:
        connection.rollback()
        logger.exception("Could not save watchlist.")
        return False
    finally:
        connection.close()


def save_scan(client_id: str, product_name: str, filename: str, extracted_text: str, ingredients: list[str], matches: list[dict]) -> int | None:
    connection = _connect()
    if connection is None:
        return None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO inci_scans (client_id, product_name, filename, extracted_text, ingredients_json, matches_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (client_id, product_name[:255], filename[:255], extracted_text, json.dumps(ingredients), json.dumps(matches)),
        )
        scan_id = int(cursor.lastrowid)
        connection.commit()
        cursor.close()
        return scan_id
    except Exception:
        connection.rollback()
        logger.exception("Could not save scan history.")
        return None
    finally:
        connection.close()


def recent_scans(client_id: str, limit: int = 10) -> list[dict] | None:
    connection = _connect()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, product_name, filename, extracted_text, ingredients_json, matches_json, created_at FROM inci_scans WHERE client_id=%s ORDER BY created_at DESC, id DESC LIMIT %s",
            (client_id, min(max(limit, 1), 25)),
        )
        rows = cursor.fetchall()
        cursor.close()
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "product_name": row["product_name"],
                "filename": row["filename"],
                "extracted_text": row["extracted_text"],
                "ingredients": json.loads(row["ingredients_json"] or "[]"),
                "matches": json.loads(row["matches_json"] or "[]"),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })
        return result
    except Exception:
        logger.exception("Could not read scan history.")
        return None
    finally:
        connection.close()


def update_scan(client_id: str, scan_id: int, extracted_text: str, ingredients: list[str], matches: list[dict]) -> bool:
    """Update a scan only when it belongs to the caller's browser workspace."""
    connection = _connect()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE inci_scans SET extracted_text=%s, ingredients_json=%s, matches_json=%s WHERE id=%s AND client_id=%s",
            (extracted_text, json.dumps(ingredients), json.dumps(matches), scan_id, client_id),
        )
        updated = cursor.rowcount > 0
        connection.commit()
        cursor.close()
        return updated
    except Exception:
        connection.rollback()
        logger.exception("Could not update corrected scan text.")
        return False
    finally:
        connection.close()
