from fastapi.testclient import TestClient

from dzshop.api import create_app


def client():
    return TestClient(create_app(":memory:", force_offline=True))


def test_chat_and_admin_flow():
    c = client()
    assert c.get("/health").json() == {"status": "ok", "mode": "offline"}
    r = c.post("/chat", json={"customer_id": "w1", "message": "ch7al soum powerbank?"}).json()
    assert "3 900 DA" in r["reply"] and r["language"] == "darija"
    assert r["tool_calls"][-1]["name"] == "get_price_and_stock"
    for m in ["bghit nakhod", "Alger", "Yacine Ould", "0699887766", "Hai Bab Ezzouar, bloc 4"]:
        r = c.post("/chat", json={"customer_id": "w1", "message": m}).json()
    assert "DZ-1003" in r["reply"]
    orders = {o["order_id"]: o for o in c.get("/api/orders").json()}
    assert orders["DZ-1003"]["status"] == "pending_confirmation"
    c.post("/chat", json={"customer_id": "w1", "message": "iyeh"})
    orders = {o["order_id"]: o for o in c.get("/api/orders").json()}
    assert orders["DZ-1003"]["status"] == "confirmed" and orders["DZ-1003"]["stage"] == "label_created"
    assert c.post("/api/orders/DZ-1003/advance").json()["stage"] == "picked_up"
    assert c.post("/api/orders/DZ-1002/advance").status_code == 404


def test_pages_and_validation():
    c = client()
    assert "text/html" in c.get("/").headers["content-type"]
    assert "Orders" in c.get("/admin").text
    assert c.post("/chat", json={"message": ""}).status_code == 422
    assert len(c.get("/api/products").json()) == 8
