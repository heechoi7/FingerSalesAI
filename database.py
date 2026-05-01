import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import pooling


load_dotenv(Path(__file__).resolve().parent / ".env")


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "database": os.getenv("MYSQL_DATABASE", "FingerSalesAI"),
    "user": os.getenv("MYSQL_USER", "crmuser"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "charset": "utf8mb4",
    "use_unicode": True,
    "connection_timeout": int(os.getenv("MYSQL_CONNECTION_TIMEOUT", "10")),
}

DEFAULT_TENANT_ID = int(os.getenv("MYSQL_TENANT_ID", "1"))
DB_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", "10"))
DB_POOL_NAME = os.getenv("MYSQL_POOL_NAME", "fingersalesai_pool")
_connection_pool: pooling.MySQLConnectionPool | None = None


def get_connection_pool() -> pooling.MySQLConnectionPool:
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name=DB_POOL_NAME,
            pool_size=DB_POOL_SIZE,
            pool_reset_session=True,
            **DB_CONFIG,
        )
    return _connection_pool


@contextmanager
def db_connection() -> Iterator[mysql.connector.MySQLConnection]:
    connection = get_connection_pool().get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME IN ('accounts', 'contacts', 'tenants', 'users')
            """
        )
        existing = {row["TABLE_NAME"] for row in cursor.fetchall()}
        missing = {"accounts", "contacts", "tenants", "users"} - existing
        if missing:
            raise RuntimeError(f"Missing required table(s): {', '.join(sorted(missing))}")


def resolve_tenant_id(tenant_id: int | None = None) -> int:
    return tenant_id or DEFAULT_TENANT_ID


def none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def datetime_to_iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def contact_row_to_customer(row: dict[str, Any]) -> dict[str, Any]:
    card_data = {
        "회사명": row.get("company_name") or "",
        "이름": row.get("contact_name") or "",
        "직무": row.get("department") or "",
        "직위": row.get("title") or "",
        "휴대전화": row.get("mobile") or "",
        "이메일": row.get("email") or "",
        "홈페이지": row.get("website") or "",
    }
    if row.get("account_phone"):
        card_data["대표전화"] = row["account_phone"]
    if row.get("address"):
        card_data["주소"] = row["address"]
    if row.get("business_no"):
        card_data["사업자등록번호"] = row["business_no"]
    if row.get("industry"):
        card_data["산업군"] = row["industry"]

    return {
        "id": row["contact_id"],
        "contact_id": row["contact_id"],
        "account_id": row.get("account_id"),
        "tenant_id": row.get("tenant_id"),
        "owner_user_id": row.get("owner_user_id"),
        "company_name": row.get("company_name") or "",
        "contact_name": row.get("contact_name") or "",
        "job_title": row.get("department") or "",
        "job_position": row.get("title") or "",
        "mobile_phone": row.get("mobile") or "",
        "email": row.get("email") or "",
        "homepage": row.get("website") or "",
        "phone": row.get("phone") or "",
        "account_phone": row.get("account_phone") or "",
        "address": row.get("address") or "",
        "business_no": row.get("business_no") or "",
        "industry": row.get("industry") or "",
        "card_data": card_data,
        "briefing": "",
        "source_file": "",
        "created_at": datetime_to_iso(row.get("created_at")),
        "updated_at": datetime_to_iso(row.get("updated_at")),
    }
