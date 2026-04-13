from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_convert_pack_to_ton() -> None:
    resp = client.post("/unit/convert", json={"productId": 501, "inputUnit": "PACK", "qty": 25})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tonQty"] == 1


def test_create_order_and_export_pdf() -> None:
    create_resp = client.post(
        "/orders",
        json={
            "customerId": 101,
            "plannedDeliveryDate": "2026-04-20",
            "items": [{"productId": 501, "inputUnit": "PACK", "qty": 25}],
            "discountAmount": 0,
            "freightAmount": 200,
        },
    )
    assert create_resp.status_code == 200
    order_id = create_resp.json()["orderId"]

    export_resp = client.post(f"/orders/{order_id}/export-pdf")
    assert export_resp.status_code == 200
    assert export_resp.json()["fileUrl"].endswith(".pdf")
