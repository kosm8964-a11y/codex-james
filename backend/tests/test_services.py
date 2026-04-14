import os
import tempfile
from decimal import Decimal


def test_create_order_and_export_pdf_with_sqlite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"

        from app import db as db_module
        from app import services

        db_module.init_db()
        services.create_finance_account(
            {
                "accountName": "测试收款户",
                "bankName": "农业银行",
                "bankAccountNo": "622200000000",
                "status": 1,
                "isDefault": 1,
            }
        )

        order = services.create_order(
            {
                "customerId": 101,
                "items": [{"productId": 501, "inputUnit": "PACK", "qty": 25}],
                "discountAmount": 0,
                "freightAmount": 0,
            }
        )
        assert order["totalAmount"] == Decimal("12500.00")

        detail = services.get_order_detail(order["orderId"])
        assert detail["orderStatus"] == "PENDING_PAYMENT"

        exported = services.export_order_pdf(order["orderId"])
        assert exported["fileUrl"].endswith(".pdf")


def test_order_status_machine_by_receipt_and_shipment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"

        from app import db as db_module
        from app import services

        db_module.init_db()
        order = services.create_order(
            {
                "customerId": 101,
                "items": [{"productId": 501, "inputUnit": "PACK", "qty": 25}],
                "discountAmount": 0,
                "freightAmount": 0,
            }
        )

        r1 = services.register_receipt(
            {
                "receivableId": order["receivableId"],
                "orderId": order["orderId"],
                "financeAccountId": 1,
                "receiptAmount": 5000,
                "receiptDate": "2026-04-13",
            }
        )
        assert r1["orderStatus"] == "PARTIAL_PAID"

        r2 = services.register_receipt(
            {
                "receivableId": order["receivableId"],
                "orderId": order["orderId"],
                "financeAccountId": 1,
                "receiptAmount": 7500,
                "receiptDate": "2026-04-13",
            }
        )
        assert r2["orderStatus"] == "PAID"

        s1 = services.update_shipment(
            order["orderId"],
            {
                "shipmentStatus": "SHIPPED",
                "shippedQtyPack": 25,
                "shippedQtyTon": 1,
                "trackingNo": "YT123",
            },
        )
        assert s1["orderStatus"] == "SHIPPED"

        s2 = services.update_shipment(
            order["orderId"],
            {
                "shipmentStatus": "DELIVERED",
                "shippedQtyPack": 25,
                "shippedQtyTon": 1,
                "trackingNo": "YT123",
            },
        )
        assert s2["orderStatus"] == "COMPLETED"

        marked = services.mark_shipment_exception(order["orderId"], "物流延迟")
        assert marked["exceptionNote"] == "物流延迟"
        shipments = services.list_shipments(status="DELIVERED")
        assert len(shipments) >= 1


def test_convert_and_accounts() -> None:
    from app.services import convert_unit

    pack_qty, ton_qty, ratio = convert_unit(501, "PACK", Decimal("25"))
    assert pack_qty == Decimal("25")
    assert ton_qty == Decimal("1")
    assert ratio == Decimal("25")

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"

        from app import db as db_module
        from app import services

        db_module.init_db()
        services.create_finance_account({"accountName": "A账户", "bankName": "工行", "bankAccountNo": "111", "status": 1, "isDefault": 1})
        a2 = services.create_finance_account({"accountName": "B账户", "bankName": "建行", "bankAccountNo": "222", "status": 1, "isDefault": 0})
        services.update_finance_account(a2["id"], {"accountName": "B账户-默认", "bankName": "建行", "bankAccountNo": "222", "status": 1, "isDefault": 1})
        active = services.list_active_finance_accounts()
        assert active[0]["id"] == a2["id"]

        s1 = services.create_supplier_bank_account({"supplierId": 9001, "accountName": "供方账户1", "bankName": "农行", "bankAccountNo": "333", "status": 1, "isDefault": 1})
        s2 = services.create_supplier_bank_account({"supplierId": 9001, "accountName": "供方账户2", "bankName": "中行", "bankAccountNo": "444", "status": 1, "isDefault": 0})
        supplier_accounts = services.list_active_supplier_bank_accounts(9001)
        assert len(supplier_accounts) == 2
        assert supplier_accounts[0]["id"] == s1["id"]
        assert supplier_accounts[1]["id"] == s2["id"]


def test_export_cash_ledger_csv() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"
        from app import db as db_module
        from app import services

        db_module.init_db()
        order = services.create_order(
            {
                "customerId": 101,
                "items": [{"productId": 501, "inputUnit": "PACK", "qty": 25}],
                "discountAmount": 0,
                "freightAmount": 0,
            }
        )
        services.register_receipt(
            {
                "receivableId": order["receivableId"],
                "orderId": order["orderId"],
                "financeAccountId": 1,
                "receiptAmount": 12500,
                "receiptDate": "2026-04-13",
            }
        )
        result = services.export_cash_ledger_csv("2026-04-01", "2026-04-30")
        assert result["total"] >= 1
        assert result["fileUrl"].endswith(".csv")
        pdf_result = services.export_cash_ledger_pdf("2026-04-01", "2026-04-30")
        assert pdf_result["total"] >= 1
        assert pdf_result["fileUrl"].endswith(".pdf")


def test_orders_filter_and_shipment_paging() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"
        from app import db as db_module
        from app import services

        db_module.init_db()
        o1 = services.create_order(
            {
                "customerId": 101,
                "items": [{"productId": 501, "inputUnit": "PACK", "qty": 25}],
                "discountAmount": 0,
                "freightAmount": 0,
            }
        )
        _o2 = services.create_order(
            {
                "customerId": 102,
                "items": [{"productId": 501, "inputUnit": "PACK", "qty": 50}],
                "discountAmount": 0,
                "freightAmount": 0,
            }
        )

        filtered = services.list_orders(customer_id=101)
        assert len(filtered) == 1
        assert filtered[0]["orderId"] == o1["orderId"]
        paged_orders = services.list_orders_paged(page=1, size=10, customer_id=101, sort_by="id", sort_dir="desc")
        assert paged_orders["total"] == 1
        assert paged_orders["rows"][0]["orderId"] == o1["orderId"]

        services.update_shipment(
            o1["orderId"],
            {"shipmentStatus": "SHIPPED", "shippedQtyPack": 25, "shippedQtyTon": 1, "trackingNo": "YT-999"},
        )
        paged = services.list_shipments_paged(page=1, size=10, status="SHIPPED", sort_by="id", sort_dir="desc")
        assert paged["total"] >= 1
        assert len(paged["rows"]) >= 1
        dashboard = services.finance_dashboard("2026-04-01", "2026-04-30")
        assert "totalIn" in dashboard
        assert "totalOut" in dashboard
        audit = services.list_audit_logs(limit=10)
        assert len(audit) >= 1


def test_user_role_management_and_authenticate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"
        from app import db as db_module
        from app import services

        db_module.init_db()
        roles = services.list_roles()
        assert any(r["roleCode"] == "admin" for r in roles)

        user = services.create_user("tester", "pass123", "测试员", 1)
        services.assign_user_roles(user["id"], ["sales"])
        users = services.list_users()
        assert any(u["username"] == "tester" for u in users)

        auth = services.authenticate_user("tester", "pass123")
        assert auth["username"] == "tester"
        assert "sales" in auth["roles"]


def test_user_lockout_and_disable_enable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OMS_DB_PATH"] = f"{tmp}/oms.db"
        from app import db as db_module
        from app import services

        db_module.init_db()
        u = services.create_user("lockuser", "abc123", "锁定测试", 1)
        services.assign_user_roles(u["id"], ["sales"])

        for _ in range(5):
            try:
                services.authenticate_user("lockuser", "wrong")
            except ValueError:
                pass

        try:
            services.authenticate_user("lockuser", "abc123")
            assert False, "should be locked"
        except ValueError as e:
            assert "locked" in str(e)

        services.unlock_user(u["id"])
        auth = services.authenticate_user("lockuser", "abc123")
        assert auth["username"] == "lockuser"

        services.set_user_status(u["id"], 0)
        try:
            services.authenticate_user("lockuser", "abc123")
            assert False, "disabled user should fail"
        except ValueError as e:
            assert "disabled" in str(e)

        services.set_user_status(u["id"], 1)
        changed = services.change_password("lockuser", "abc123", "newabc123")
        assert changed["changed"] is True
        auth2 = services.authenticate_user("lockuser", "newabc123")
        assert auth2["username"] == "lockuser"
