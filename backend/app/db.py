import os
import sqlite3
from pathlib import Path

from .auth import hash_password

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "storage" / "oms.db"


def get_conn() -> sqlite3.Connection:
    db_path = Path(os.getenv("OMS_DB_PATH", str(DEFAULT_DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            order_status TEXT NOT NULL,
            total_amount TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty_pack TEXT NOT NULL,
            qty_ton TEXT NOT NULL,
            unit_price TEXT NOT NULL,
            line_amount TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS finance_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            bank_account_no TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS supplier_bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            bank_account_no TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS finance_receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount_due TEXT NOT NULL,
            amount_received TEXT NOT NULL DEFAULT '0',
            status TEXT NOT NULL DEFAULT 'OPEN',
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS shipment_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            shipment_status TEXT NOT NULL DEFAULT 'PENDING',
            shipped_qty_pack TEXT NOT NULL DEFAULT '0',
            shipped_qty_ton TEXT NOT NULL DEFAULT '0',
            tracking_no TEXT,
            exception_note TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS order_pdf_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            file_url TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS finance_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receivable_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            finance_account_id INTEGER,
            receipt_amount TEXT NOT NULL,
            receipt_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS finance_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payable_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            supplier_bank_account_id INTEGER,
            payment_amount TEXT NOT NULL,
            payment_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cash_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,
            amount TEXT NOT NULL,
            occur_date TEXT NOT NULL,
            biz_type TEXT NOT NULL,
            biz_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            action TEXT NOT NULL,
            operator TEXT NOT NULL,
            biz_id INTEGER,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            display_name TEXT,
            status INTEGER NOT NULL DEFAULT 1,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_code TEXT NOT NULL UNIQUE,
            role_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        """
    )
    cur.execute("INSERT OR IGNORE INTO roles(role_code, role_name) VALUES ('admin', '管理员')")
    cur.execute("INSERT OR IGNORE INTO roles(role_code, role_name) VALUES ('finance', '财务')")
    cur.execute("INSERT OR IGNORE INTO roles(role_code, role_name) VALUES ('sales', '销售')")
    cur.execute("INSERT OR IGNORE INTO roles(role_code, role_name) VALUES ('warehouse', '仓库')")
    cur.execute(
        "INSERT OR IGNORE INTO users(username, password, display_name, status, failed_attempts, locked_until) VALUES (?, ?, ?, 1, 0, 0)",
        ("admin", hash_password("admin123"), "系统管理员"),
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO user_roles(user_id, role_id)
        SELECT u.id, r.id FROM users u, roles r
        WHERE u.username='admin' AND r.role_code='admin'
        """
    )
    conn.commit()
    conn.close()


init_db()
