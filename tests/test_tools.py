import pytest

from dzshop.guard import PriceStockGuard
from dzshop.tools import find_wilaya, normalize_phone

ORDER = dict(customer_name="Karim Benali", phone="0661234567", wilaya="Oran", address="Cité 500 logements",
             items=[{"sku": "MON-01", "qty": 2}])


@pytest.mark.parametrize("raw,ok", [
    ("0661234567", "0661234567"), ("06 61 23 45 67", "0661234567"), ("+213661234567", "0661234567"),
    ("0555-12-34-56", "0555123456"), ("0771234567", "0771234567"),
    ("0461234567", None), ("066123456", None), ("06612345678", None), ("abc", None), ("", None),
])
def test_phone_validation(raw, ok):
    assert normalize_phone(raw) == ok


def test_find_wilaya_spellings():
    assert find_wilaya("tawsil l wahran") == "Oran"
    assert find_wilaya("livraison à Sétif svp") == "Sétif"
    assert find_wilaya("قسنطينة") == "Constantine"
    assert find_wilaya("rien ici") is None


def test_search_products_multilingual(tools):
    assert tools.search_products("ch7al soum la mountra")["products"][0]["sku"] == "MON-01"
    assert tools.search_products("sabat running")["products"][0]["sku"] == "CHA-04"
    assert tools.search_products("حقيبة")["products"][0]["sku"] == "SAC-03"
    assert tools.search_products("zzzz qqqq")["count"] == 0
    assert tools.search_products("")["count"] == 5


def test_price_and_stock_from_db(tools):
    r = tools.get_price_and_stock("MON-01")
    assert (r["price_dzd"], r["stock"], r["in_stock"]) == (6500, 14, True)
    assert tools.get_price_and_stock("CHA-04")["in_stock"] is False
    bad = tools.get_price_and_stock("NOPE-99")
    assert not bad["ok"] and bad["error"] == "unknown_product" and "price_dzd" not in bad


def test_quote_shipping(tools):
    assert tools.quote_shipping("Oran")["fee_dzd"] == 600
    assert tools.quote_shipping("wahran")["wilaya"] == "Oran"
    r = tools.quote_shipping("Tamanrasset")
    assert r["error"] == "wilaya_not_covered" and "Alger" in r["covered"]


def test_create_order_computes_totals_from_db(tools):
    r = tools.create_cod_order(**ORDER)
    assert r["ok"] and r["subtotal_dzd"] == 13000 and r["shipping_fee_dzd"] == 600 and r["total_dzd"] == 13600
    assert r["status"] == "pending_confirmation" and r["order_id"].startswith("DZ-")


@pytest.mark.parametrize("patch,err", [
    ({"phone": "0461234567"}, "invalid_phone"), ({"customer_name": " "}, "invalid_name"),
    ({"address": "x"}, "invalid_address"), ({"wilaya": "Mars"}, "wilaya_not_covered"),
    ({"items": []}, "empty_order"), ({"items": [{"sku": "NOPE", "qty": 1}]}, "unknown_product"),
    ({"items": [{"sku": "MON-01", "qty": 0}]}, "invalid_quantity"),
    ({"items": [{"sku": "CHA-04", "qty": 1}]}, "insufficient_stock"),
    ({"items": [{"sku": "SAC-03", "qty": 10}]}, "insufficient_stock"),
])
def test_create_order_rejections(tools, patch, err):
    r = tools.create_cod_order(**{**ORDER, **patch})
    assert not r["ok"] and r["error"] == err


def test_confirm_flow_and_stock_decrement(tools):
    o = tools.create_cod_order(**ORDER)
    assert tools.confirm_order(o["order_id"], "0999999999")["error"] == "phone_mismatch"
    c = tools.confirm_order(o["order_id"], "06 61 23 45 67")
    assert c["ok"] and c["status"] == "confirmed" and c["tracking_code"].startswith("DZT")
    assert tools.get_price_and_stock("MON-01")["stock"] == 12
    assert tools.confirm_order(o["order_id"], "0661234567")["error"] == "not_pending"
    assert tools.cancel_order(o["order_id"], "0661234567")["error"] == "not_cancellable"


def test_cancel_pending(tools):
    o = tools.create_cod_order(**ORDER)
    assert tools.cancel_order(o["order_id"], "0661234567")["status"] == "cancelled"
    assert tools.get_order_status(o["order_id"], "0661234567")["status"] == "cancelled"


def test_order_status_and_tracking_seed_order(tools):
    s = tools.get_order_status("DZ-1001", "0555123456")
    assert s["ok"] and s["status"] == "shipped" and s["total_dzd"] == 3800
    t = tools.track_shipment("DZ-1001", "0555123456")
    assert t["current_stage"] == "at_local_hub" and len(t["events"]) == 4
    assert tools.track_shipment("DZ-1001", "0661111111")["error"] == "phone_mismatch"
    assert tools.get_order_status("DZ-9999", "0555123456")["error"] == "order_not_found"
    assert tools.track_shipment("DZ-1002", "0661000000")["error"] == "no_shipment"
    assert tools.get_order_status("bad", "0555123456")["error"] == "invalid_order_id"


def test_tracking_advances_to_delivered(db, tools):
    from dzshop import tracking
    for _ in range(2):
        tracking.advance(db, "DZT100100")
    assert tools.track_shipment("DZ-1001", "0555123456")["current_stage"] == "delivered"
    assert tracking.advance(db, "DZT100100") is None
    assert tools.get_order_status("DZ-1001", "0555123456")["status"] == "delivered"


def test_escalate(tools, db):
    assert tools.escalate_to_human("  ")["error"] == "reason_required"
    r = tools.escalate_to_human("refund request", session_id="s1")
    assert r["ok"] and db.one("SELECT reason, session_id FROM escalations")["reason"] == "refund request"


def test_dispatch_errors(tools):
    assert tools.call("nope", {})["error"] == "unknown_tool"
    assert tools.call("get_price_and_stock", {})["error"] == "bad_arguments"
    assert tools.call("escalate_to_human", {"reason": "x"}, session_id="a")["ok"]


def test_guard_blocks_invented_numbers(tools):
    g = PriceStockGuard()
    g.observe(tools.get_price_and_stock("MON-01"))
    assert g.check("La montre coûte 6 500 DA, 14 pièces en stock") == []
    assert g.check("Prix: 5 000 DA") == ["price 5000"]
    assert g.check("السعر 4500 دج") == ["price 4500"]
    assert g.check("Il reste 3 pièces en stock") == ["stock 3"]
    assert g.check("pas de chiffre ici, 2 × montre") == []
