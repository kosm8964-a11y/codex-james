from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import time

from .auth import hash_password, verify_password
from .db import get_conn


PRODUCT_RULES = {501: Decimal("25"), 502: Decimal("20")}
CUSTOMER_PRODUCT_PRICE = {(101, 501): Decimal("500"), (101, 502): Decimal("650")}
DEFAULT_PRODUCT_PRICE = {501: Decimal("520"), 502: Decimal("680")}

BASE_DIR = Path(__file__).resolve().parents[1]
CONTRACT_DIR = BASE_DIR / "storage" / "contracts"
CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = BASE_DIR / "storage" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


class _StoreView:
    @property
    def cash_ledger(self) -> list[dict]:
        conn = get_conn()
        rows = conn.execute("SELECT direction, amount, occur_date, biz_type, biz_id FROM cash_ledger ORDER BY id DESC").fetchall()
        conn.close()
        return [{"direction": x["direction"], "amount": Decimal(x["amount"]), "occurDate": x["occur_date"], "bizType": x["biz_type"], "bizId": x["biz_id"]} for x in rows]


store = _StoreView()


def write_audit_log(module_name: str, action: str, operator: str, biz_id: int | None = None, note: str | None = None) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_logs(module_name, action, operator, biz_id, note) VALUES (?, ?, ?, ?, ?)",
        (module_name, action, operator, biz_id, note),
    )
    conn.commit()
    conn.close()


def list_audit_logs(module_name: str | None = None, limit: int = 100) -> list[dict]:
    conn = get_conn()
    if module_name:
        rows = conn.execute(
            "SELECT module_name, action, operator, biz_id, note, created_at FROM audit_logs WHERE module_name=? ORDER BY id DESC LIMIT ?",
            (module_name, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT module_name, action, operator, biz_id, note, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {
            "moduleName": x["module_name"],
            "action": x["action"],
            "operator": x["operator"],
            "bizId": x["biz_id"],
            "note": x["note"],
            "createdAt": x["created_at"],
        }
        for x in rows
    ]


def list_roles() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, role_code, role_name FROM roles ORDER BY id").fetchall()
    conn.close()
    return [{"id": x["id"], "roleCode": x["role_code"], "roleName": x["role_name"]} for x in rows]


def list_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.status,
               GROUP_CONCAT(r.role_code) AS roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        GROUP BY u.id, u.username, u.display_name, u.status
        ORDER BY u.id DESC
        """
    ).fetchall()
    conn.close()
    return [
        {
            "id": x["id"],
            "username": x["username"],
            "displayName": x["display_name"],
            "status": x["status"],
            "roles": [] if not x["roles"] else x["roles"].split(","),
        }
        for x in rows
    ]


def create_user(username: str, password: str, display_name: str | None = None, status: int = 1) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users(username, password, display_name, status, failed_attempts, locked_until) VALUES (?, ?, ?, ?, 0, 0)",
        (username, hash_password(password), display_name, status),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    write_audit_log("users", "create", "system", user_id, f"username={username}")
    return {"id": user_id, "username": username, "displayName": display_name, "status": status}


def assign_user_roles(user_id: int, role_codes: list[str]) -> dict:
    conn = get_conn()
    user = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise KeyError("用户不存在")
    conn.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
    for code in role_codes:
        role = conn.execute("SELECT id FROM roles WHERE role_code=?", (code,)).fetchone()
        if role:
            conn.execute("INSERT INTO user_roles(user_id, role_id) VALUES (?, ?)", (user_id, role["id"]))
    conn.commit()
    conn.close()
    write_audit_log("users", "assign_roles", "system", user_id, ",".join(role_codes))
    return {"userId": user_id, "roles": role_codes}


def authenticate_user(username: str, password: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT id, username, password, status, failed_attempts, locked_until FROM users WHERE username=?", (username,)).fetchone()
    now = int(time.time())
    if not row:
        conn.close()
        raise ValueError("invalid credentials")
    if row["status"] != 1:
        conn.close()
        raise ValueError("user disabled")
    if row["locked_until"] and row["locked_until"] > now:
        conn.close()
        raise ValueError("user temporarily locked")
    if not verify_password(password, row["password"]):
        attempts = int(row["failed_attempts"]) + 1
        locked_until = now + 900 if attempts >= 5 else 0
        conn.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?", (0 if attempts >= 5 else attempts, locked_until, row["id"]))
        conn.commit()
        conn.close()
        raise ValueError("invalid credentials")
    conn.execute("UPDATE users SET failed_attempts=0, locked_until=0 WHERE id=?", (row["id"],))
    conn.commit()
    roles = conn.execute(
        "SELECT r.role_code FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=? ORDER BY r.id",
        (row["id"],),
    ).fetchall()
    conn.close()
    role_codes = [x["role_code"] for x in roles] or ["sales"]
    return {"userId": row["id"], "username": row["username"], "roles": role_codes}


def set_user_status(user_id: int, status: int) -> dict:
    conn = get_conn()
    found = conn.execute("SELECT id, username FROM users WHERE id=?", (user_id,)).fetchone()
    if not found:
        conn.close()
        raise KeyError("用户不存在")
    conn.execute("UPDATE users SET status=?, failed_attempts=0, locked_until=0 WHERE id=?", (status, user_id))
    conn.commit()
    conn.close()
    write_audit_log("users", "set_status", "system", user_id, f"status={status}")
    return {"userId": user_id, "status": status}


def quant_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resolve_price(customer_id: int, product_id: int) -> tuple[str, Decimal]:
    if (customer_id, product_id) in CUSTOMER_PRODUCT_PRICE:
        return "CUSTOMER_SPECIAL", CUSTOMER_PRODUCT_PRICE[(customer_id, product_id)]
    return "STANDARD", DEFAULT_PRODUCT_PRICE.get(product_id, Decimal("0"))


def convert_unit(product_id: int, input_unit: str, qty: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    ratio = PRODUCT_RULES.get(product_id)
    if not ratio:
        raise ValueError("产品未配置包吨换算规则")
    return (qty, qty / ratio, ratio) if input_unit == "PACK" else (qty * ratio, qty, ratio)


def _make_order_no(order_id: int) -> str:
    return f"SO{date.today().strftime('%Y%m%d')}{order_id:06d}"


def _refresh_order_status(conn, order_id: int) -> str:
    recv = conn.execute("SELECT amount_due, amount_received FROM finance_receivables WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    ship = conn.execute("SELECT shipment_status FROM shipment_records WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    amount_due = Decimal(recv["amount_due"]) if recv else Decimal("0")
    amount_received = Decimal(recv["amount_received"]) if recv else Decimal("0")
    shipment_status = ship["shipment_status"] if ship else "PENDING"

    if amount_received <= Decimal("0"):
        status = "PENDING_PAYMENT"
    elif amount_received < amount_due:
        status = "PARTIAL_PAID"
    else:
        if shipment_status == "DELIVERED":
            status = "COMPLETED"
        elif shipment_status == "SHIPPED":
            status = "SHIPPED"
        else:
            status = "PAID"

    conn.execute("UPDATE orders SET order_status=? WHERE id=?", (status, order_id))
    return status


def list_active_finance_accounts() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, account_name, bank_name, bank_account_no, status, is_default FROM finance_accounts WHERE status=1 ORDER BY is_default DESC, id DESC").fetchall()
    conn.close()
    return [{"id": x["id"], "accountName": x["account_name"], "bankName": x["bank_name"], "bankAccountNo": x["bank_account_no"], "status": x["status"], "isDefault": x["is_default"]} for x in rows]


def create_finance_account(payload: dict) -> dict:
    conn = get_conn()
    if payload.get("isDefault", 0) == 1:
        conn.execute("UPDATE finance_accounts SET is_default=0")
    cur = conn.execute(
        "INSERT INTO finance_accounts(account_name, bank_name, bank_account_no, status, is_default) VALUES (?, ?, ?, ?, ?)",
        (payload["accountName"], payload["bankName"], payload["bankAccountNo"], payload.get("status", 1), payload.get("isDefault", 0)),
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid, **payload}


def update_finance_account(account_id: int, payload: dict) -> dict:
    conn = get_conn()
    if not conn.execute("SELECT id FROM finance_accounts WHERE id=?", (account_id,)).fetchone():
        conn.close()
        raise KeyError("收款账户不存在")
    if payload.get("isDefault", 0) == 1:
        conn.execute("UPDATE finance_accounts SET is_default=0")
    conn.execute(
        "UPDATE finance_accounts SET account_name=?, bank_name=?, bank_account_no=?, status=?, is_default=? WHERE id=?",
        (payload["accountName"], payload["bankName"], payload["bankAccountNo"], payload.get("status", 1), payload.get("isDefault", 0), account_id),
    )
    conn.commit()
    conn.close()
    return {"id": account_id, **payload}


def list_active_supplier_bank_accounts(supplier_id: int | None = None) -> list[dict]:
    conn = get_conn()
    if supplier_id:
        rows = conn.execute("SELECT id, supplier_id, account_name, bank_name, bank_account_no, status, is_default FROM supplier_bank_accounts WHERE status=1 AND supplier_id=? ORDER BY is_default DESC, id DESC", (supplier_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id, supplier_id, account_name, bank_name, bank_account_no, status, is_default FROM supplier_bank_accounts WHERE status=1 ORDER BY is_default DESC, id DESC").fetchall()
    conn.close()
    return [{"id": x["id"], "supplierId": x["supplier_id"], "accountName": x["account_name"], "bankName": x["bank_name"], "bankAccountNo": x["bank_account_no"], "status": x["status"], "isDefault": x["is_default"]} for x in rows]


def create_supplier_bank_account(payload: dict) -> dict:
    conn = get_conn()
    if payload.get("isDefault", 0) == 1:
        conn.execute("UPDATE supplier_bank_accounts SET is_default=0 WHERE supplier_id=?", (payload["supplierId"],))
    cur = conn.execute(
        "INSERT INTO supplier_bank_accounts(supplier_id, account_name, bank_name, bank_account_no, status, is_default) VALUES (?, ?, ?, ?, ?, ?)",
        (payload["supplierId"], payload["accountName"], payload["bankName"], payload["bankAccountNo"], payload.get("status", 1), payload.get("isDefault", 0)),
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid, **payload}


def create_order(payload: dict) -> dict:
    subtotal = Decimal("0")
    normalized_items: list[dict] = []
    for item in payload["items"]:
        pack_qty, ton_qty, _ = convert_unit(item["productId"], item["inputUnit"], Decimal(str(item["qty"])))
        _, price = resolve_price(payload["customerId"], item["productId"])
        base_qty = pack_qty if item["inputUnit"] == "PACK" else ton_qty
        line_amount = quant_money(base_qty * price)
        subtotal += line_amount
        normalized_items.append({"productId": item["productId"], "qtyPack": pack_qty, "qtyTon": ton_qty, "unitPrice": price, "lineAmount": line_amount})

    total = quant_money(subtotal - Decimal(str(payload.get("discountAmount", 0))) + Decimal(str(payload.get("freightAmount", 0))))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO orders(order_no, customer_id, order_status, total_amount) VALUES (?, ?, ?, ?)", ("TEMP", payload["customerId"], "PENDING_PAYMENT", str(total)))
    order_id = cur.lastrowid
    order_no = _make_order_no(order_id)
    cur.execute("UPDATE orders SET order_no=? WHERE id=?", (order_no, order_id))
    for item in normalized_items:
        cur.execute("INSERT INTO order_items(order_id, product_id, qty_pack, qty_ton, unit_price, line_amount) VALUES (?, ?, ?, ?, ?, ?)", (order_id, item["productId"], str(item["qtyPack"]), str(item["qtyTon"]), str(item["unitPrice"]), str(item["lineAmount"])))
    cur.execute("INSERT INTO finance_receivables(order_id, amount_due, amount_received, status) VALUES (?, ?, '0', 'OPEN')", (order_id, str(total)))
    receivable_id = cur.lastrowid
    cur.execute("INSERT INTO shipment_records(order_id, shipment_status) VALUES (?, 'PENDING')", (order_id,))
    shipment_id = cur.lastrowid
    conn.commit()
    conn.close()
    write_audit_log("orders", "create", payload.get("operator", "system"), order_id, f"orderNo={order_no}")
    return {"orderId": order_id, "orderNo": order_no, "orderStatus": "PENDING_PAYMENT", "totalAmount": total, "items": normalized_items, "receivableId": receivable_id, "shipmentRecordId": shipment_id}


def update_shipment(order_id: int, payload: dict) -> dict:
    conn = get_conn()
    if not conn.execute("SELECT id FROM orders WHERE id=?", (order_id,)).fetchone():
        conn.close()
        raise KeyError("订单不存在")
    conn.execute(
        "UPDATE shipment_records SET shipment_status=?, shipped_qty_pack=?, shipped_qty_ton=?, tracking_no=? WHERE id=(SELECT id FROM shipment_records WHERE order_id=? ORDER BY id DESC LIMIT 1)",
        (payload["shipmentStatus"], str(payload.get("shippedQtyPack", 0)), str(payload.get("shippedQtyTon", 0)), payload.get("trackingNo"), order_id),
    )
    status = _refresh_order_status(conn, order_id)
    shipment = conn.execute("SELECT shipment_status, shipped_qty_pack, shipped_qty_ton, tracking_no, exception_note FROM shipment_records WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    conn.commit()
    conn.close()
    write_audit_log("shipments", "update", payload.get("operator", "system"), order_id, f"status={payload['shipmentStatus']}")
    return {"orderId": order_id, "orderStatus": status, "shipment": {"status": shipment["shipment_status"], "shippedQtyPack": Decimal(shipment["shipped_qty_pack"]), "shippedQtyTon": Decimal(shipment["shipped_qty_ton"]), "trackingNo": shipment["tracking_no"], "exceptionNote": shipment["exception_note"]}}


def list_shipments(status: str | None = None, order_id: int | None = None, tracking_no: str | None = None) -> list[dict]:
    conn = get_conn()
    query = "SELECT order_id, shipment_status, shipped_qty_pack, shipped_qty_ton, tracking_no, exception_note FROM shipment_records WHERE 1=1"
    params: list = []
    if status:
        query += " AND shipment_status=?"
        params.append(status)
    if order_id:
        query += " AND order_id=?"
        params.append(order_id)
    if tracking_no:
        query += " AND tracking_no LIKE ?"
        params.append(f"%{tracking_no}%")
    query += " ORDER BY id DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [
        {
            "orderId": x["order_id"],
            "status": x["shipment_status"],
            "shippedQtyPack": Decimal(x["shipped_qty_pack"]),
            "shippedQtyTon": Decimal(x["shipped_qty_ton"]),
            "trackingNo": x["tracking_no"],
            "exceptionNote": x["exception_note"],
        }
        for x in rows
    ]


def mark_shipment_exception(order_id: int, exception_note: str) -> dict:
    conn = get_conn()
    exists = conn.execute("SELECT id FROM shipment_records WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    if not exists:
        conn.close()
        raise KeyError("发货记录不存在")
    conn.execute("UPDATE shipment_records SET exception_note=? WHERE id=?", (exception_note, exists["id"]))
    shipment = conn.execute("SELECT shipment_status, shipped_qty_pack, shipped_qty_ton, tracking_no, exception_note FROM shipment_records WHERE id=?", (exists["id"],)).fetchone()
    conn.commit()
    conn.close()
    return {
        "orderId": order_id,
        "status": shipment["shipment_status"],
        "shippedQtyPack": Decimal(shipment["shipped_qty_pack"]),
        "shippedQtyTon": Decimal(shipment["shipped_qty_ton"]),
        "trackingNo": shipment["tracking_no"],
        "exceptionNote": shipment["exception_note"],
    }


def get_order_detail(order_id: int) -> dict:
    conn = get_conn()
    order = conn.execute("SELECT id, order_no, customer_id, order_status, total_amount FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close()
        raise KeyError("订单不存在")
    items = conn.execute("SELECT product_id, qty_pack, qty_ton, unit_price, line_amount FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    shipment = conn.execute("SELECT shipment_status, shipped_qty_pack, shipped_qty_ton, tracking_no, exception_note FROM shipment_records WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    receivable = conn.execute("SELECT id, amount_due, amount_received, status FROM finance_receivables WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    receipts = conn.execute("SELECT receipt_amount, receipt_date, finance_account_id FROM finance_receipts WHERE order_id=? ORDER BY id DESC", (order_id,)).fetchall()
    conn.close()
    return {
        "orderId": order["id"],
        "orderNo": order["order_no"],
        "customerId": order["customer_id"],
        "orderStatus": order["order_status"],
        "totalAmount": Decimal(order["total_amount"]),
        "items": [{"productId": x["product_id"], "qtyPack": Decimal(x["qty_pack"]), "qtyTon": Decimal(x["qty_ton"]), "unitPrice": Decimal(x["unit_price"]), "lineAmount": Decimal(x["line_amount"])} for x in items],
        "shipment": None if not shipment else {"status": shipment["shipment_status"], "shippedQtyPack": Decimal(shipment["shipped_qty_pack"]), "shippedQtyTon": Decimal(shipment["shipped_qty_ton"]), "trackingNo": shipment["tracking_no"], "exceptionNote": shipment["exception_note"]},
        "receivable": None if not receivable else {"receivableId": receivable["id"], "amountDue": Decimal(receivable["amount_due"]), "amountReceived": Decimal(receivable["amount_received"]), "status": receivable["status"]},
        "receipts": [{"amount": Decimal(x["receipt_amount"]), "date": x["receipt_date"], "financeAccountId": x["finance_account_id"]} for x in receipts],
    }


def _escape_pdf_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines: list[str]) -> bytes:
    y = 780
    content_parts = ["BT /F1 12 Tf"]
    for line in lines:
        content_parts.append(f"1 0 0 1 40 {y} Tm ({_escape_pdf_text(line)}) Tj")
        y -= 18
    content_parts.append("ET")
    content = "\n".join(content_parts).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(content)} >> stream\n".encode() + content + b"\nendstream endobj\n",
    ]
    out = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out += obj
    xref_start = len(out)
    out += f"xref\n0 {len(offsets)}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    return out


def export_order_pdf(order_id: int) -> dict:
    conn = get_conn()
    order = conn.execute("SELECT id, order_no, customer_id, total_amount FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close()
        raise KeyError("订单不存在")
    items = conn.execute("SELECT product_id, qty_pack, qty_ton, unit_price, line_amount FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    default_account = conn.execute("SELECT account_name, bank_name, bank_account_no FROM finance_accounts WHERE status=1 ORDER BY is_default DESC, id DESC LIMIT 1").fetchone()
    lines = [f"Order No: {order['order_no']}", f"Customer ID: {order['customer_id']}", f"Total Amount: {order['total_amount']}"]
    if default_account:
        lines += [f"Payee: {default_account['account_name']}", f"Bank: {default_account['bank_name']}", f"Account: {default_account['bank_account_no']}"]
    lines.append("Items:")
    for idx, item in enumerate(items, 1):
        lines.append(f"{idx}. P{item['product_id']} pack={item['qty_pack']} ton={item['qty_ton']} price={item['unit_price']} amount={item['line_amount']}")
    pdf_path = CONTRACT_DIR / f"{order['order_no']}.pdf"
    pdf_path.write_bytes(_build_simple_pdf(lines))
    file_url = f"/storage/contracts/{order['order_no']}.pdf"
    conn.execute("INSERT INTO order_pdf_exports(order_id, file_url) VALUES (?, ?)", (order_id, file_url))
    export_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    return {"exportId": export_id, "fileUrl": file_url}


def register_receipt(payload: dict) -> dict:
    conn = get_conn()
    rec = conn.execute("SELECT id, amount_received FROM finance_receivables WHERE id=?", (payload["receivableId"],)).fetchone()
    if not rec:
        conn.close()
        raise KeyError("应收记录不存在")
    amount = Decimal(str(payload["receiptAmount"]))
    new_amount = quant_money(Decimal(rec["amount_received"]) + amount)
    conn.execute("UPDATE finance_receivables SET amount_received=? WHERE id=?", (str(new_amount), payload["receivableId"]))
    conn.execute("INSERT INTO finance_receipts(receivable_id, order_id, finance_account_id, receipt_amount, receipt_date) VALUES (?, ?, ?, ?, ?)", (payload["receivableId"], payload["orderId"], payload.get("financeAccountId"), str(amount), str(payload["receiptDate"])))
    conn.execute("INSERT INTO cash_ledger(direction, amount, occur_date, biz_type, biz_id) VALUES ('IN', ?, ?, 'RECEIPT', ?)", (str(amount), str(payload["receiptDate"]), payload["receivableId"]))
    status = _refresh_order_status(conn, payload["orderId"])
    conn.commit()
    conn.close()
    write_audit_log("finance_receipts", "create", payload.get("operator", "system"), payload["orderId"], f"amount={amount}")
    return {"receivableId": payload["receivableId"], "orderId": payload["orderId"], "receivedAmount": new_amount, "orderStatus": status}


def register_payment(payload: dict) -> dict:
    amount = Decimal(str(payload["paymentAmount"]))
    conn = get_conn()
    conn.execute(
        "INSERT INTO finance_payments(payable_id, supplier_id, supplier_bank_account_id, payment_amount, payment_date) VALUES (?, ?, ?, ?, ?)",
        (payload["payableId"], payload["supplierId"], payload.get("supplierBankAccountId"), str(amount), str(payload["paymentDate"])),
    )
    conn.execute("INSERT INTO cash_ledger(direction, amount, occur_date, biz_type, biz_id) VALUES ('OUT', ?, ?, 'PAYMENT', ?)", (str(amount), str(payload["paymentDate"]), payload["payableId"]))
    conn.commit()
    conn.close()
    return {"payableId": payload["payableId"], "supplierId": payload["supplierId"], "supplierBankAccountId": payload.get("supplierBankAccountId"), "paymentAmount": amount}


def export_cash_ledger_csv(date_from: str | None = None, date_to: str | None = None) -> dict:
    conn = get_conn()
    query = "SELECT direction, amount, occur_date, biz_type, biz_id FROM cash_ledger WHERE 1=1"
    params: list = []
    if date_from:
        query += " AND occur_date>=?"
        params.append(date_from)
    if date_to:
        query += " AND occur_date<=?"
        params.append(date_to)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    file_name = f"cash_ledger_{date.today().strftime('%Y%m%d')}.csv"
    file_path = REPORT_DIR / file_name
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["direction", "amount", "occur_date", "biz_type", "biz_id"])
        for row in rows:
            writer.writerow([row["direction"], row["amount"], row["occur_date"], row["biz_type"], row["biz_id"]])

    return {"fileUrl": f"/storage/reports/{file_name}", "total": len(rows)}


def export_cash_ledger_pdf(date_from: str | None = None, date_to: str | None = None) -> dict:
    conn = get_conn()
    query = "SELECT direction, amount, occur_date, biz_type, biz_id FROM cash_ledger WHERE 1=1"
    params: list = []
    if date_from:
        query += " AND occur_date>=?"
        params.append(date_from)
    if date_to:
        query += " AND occur_date<=?"
        params.append(date_to)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    lines = [
        "Cash Ledger Reconciliation",
        f"From: {date_from or '-'} To: {date_to or '-'}",
        f"Total Rows: {len(rows)}",
    ]
    total_in = Decimal("0")
    total_out = Decimal("0")
    for row in rows:
        amount = Decimal(row["amount"])
        if row["direction"] == "IN":
            total_in += amount
        else:
            total_out += amount
        lines.append(f"{row['occur_date']} {row['direction']} {row['amount']} {row['biz_type']}#{row['biz_id']}")
    lines.append(f"Summary IN={total_in} OUT={total_out} NET={total_in-total_out}")

    file_name = f"cash_ledger_{date.today().strftime('%Y%m%d')}.pdf"
    file_path = REPORT_DIR / file_name
    file_path.write_bytes(_build_simple_pdf(lines))
    return {"fileUrl": f"/storage/reports/{file_name}", "total": len(rows)}


def list_shipments_paged(
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    order_id: int | None = None,
    tracking_no: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "desc",
) -> dict:
    safe_sort_by = sort_by if sort_by in {"id", "order_id", "shipment_status"} else "id"
    safe_sort_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    offset = max(page - 1, 0) * size

    conn = get_conn()
    where = " WHERE 1=1"
    params: list = []
    if status:
        where += " AND shipment_status=?"
        params.append(status)
    if order_id:
        where += " AND order_id=?"
        params.append(order_id)
    if tracking_no:
        where += " AND tracking_no LIKE ?"
        params.append(f"%{tracking_no}%")

    total = conn.execute(f"SELECT COUNT(1) AS c FROM shipment_records {where}", tuple(params)).fetchone()["c"]
    rows = conn.execute(
        f"SELECT id, order_id, shipment_status, shipped_qty_pack, shipped_qty_ton, tracking_no, exception_note FROM shipment_records {where} ORDER BY {safe_sort_by} {safe_sort_dir} LIMIT ? OFFSET ?",
        tuple(params + [size, offset]),
    ).fetchall()
    conn.close()
    return {
        "page": page,
        "size": size,
        "total": total,
        "rows": [
            {
                "id": x["id"],
                "orderId": x["order_id"],
                "status": x["shipment_status"],
                "shippedQtyPack": Decimal(x["shipped_qty_pack"]),
                "shippedQtyTon": Decimal(x["shipped_qty_ton"]),
                "trackingNo": x["tracking_no"],
                "exceptionNote": x["exception_note"],
            }
            for x in rows
        ],
    }


def list_orders(customer_id: int | None = None, status: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    conn = get_conn()
    query = "SELECT id, order_no, customer_id, order_status, total_amount, created_at FROM orders WHERE 1=1"
    params: list = []
    if customer_id:
        query += " AND customer_id=?"
        params.append(customer_id)
    if status:
        query += " AND order_status=?"
        params.append(status)
    if date_from:
        query += " AND date(created_at)>=date(?)"
        params.append(date_from)
    if date_to:
        query += " AND date(created_at)<=date(?)"
        params.append(date_to)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [
        {
            "orderId": x["id"],
            "orderNo": x["order_no"],
            "customerId": x["customer_id"],
            "orderStatus": x["order_status"],
            "totalAmount": Decimal(x["total_amount"]),
            "createdAt": x["created_at"],
        }
        for x in rows
    ]


def list_orders_paged(
    page: int = 1,
    size: int = 20,
    customer_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "desc",
) -> dict:
    safe_sort_by = sort_by if sort_by in {"id", "created_at", "total_amount"} else "id"
    safe_sort_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    offset = max(page - 1, 0) * size

    conn = get_conn()
    where = " WHERE 1=1"
    params: list = []
    if customer_id:
        where += " AND customer_id=?"
        params.append(customer_id)
    if status:
        where += " AND order_status=?"
        params.append(status)
    if date_from:
        where += " AND date(created_at)>=date(?)"
        params.append(date_from)
    if date_to:
        where += " AND date(created_at)<=date(?)"
        params.append(date_to)

    total = conn.execute(f"SELECT COUNT(1) AS c FROM orders {where}", tuple(params)).fetchone()["c"]
    rows = conn.execute(
        f"SELECT id, order_no, customer_id, order_status, total_amount, created_at FROM orders {where} ORDER BY {safe_sort_by} {safe_sort_dir} LIMIT ? OFFSET ?",
        tuple(params + [size, offset]),
    ).fetchall()
    conn.close()
    return {
        "page": page,
        "size": size,
        "total": total,
        "rows": [
            {
                "orderId": x["id"],
                "orderNo": x["order_no"],
                "customerId": x["customer_id"],
                "orderStatus": x["order_status"],
                "totalAmount": Decimal(x["total_amount"]),
                "createdAt": x["created_at"],
            }
            for x in rows
        ],
    }


def finance_dashboard(date_from: str | None = None, date_to: str | None = None) -> dict:
    conn = get_conn()
    query = "SELECT direction, amount FROM cash_ledger WHERE 1=1"
    params: list = []
    if date_from:
        query += " AND occur_date>=?"
        params.append(date_from)
    if date_to:
        query += " AND occur_date<=?"
        params.append(date_to)
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    total_in = Decimal("0")
    total_out = Decimal("0")
    for row in rows:
        amount = Decimal(row["amount"])
        if row["direction"] == "IN":
            total_in += amount
        else:
            total_out += amount
    return {
        "totalIn": quant_money(total_in),
        "totalOut": quant_money(total_out),
        "netCashflow": quant_money(total_in - total_out),
        "ledgerCount": len(rows),
    }
