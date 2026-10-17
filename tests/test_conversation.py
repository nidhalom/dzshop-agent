from dzshop.guard import PriceStockGuard
from dzshop.offline import OfflineAgent, extract_phone, extract_qty


def names(reply):
    return [c.name for c in reply.tool_calls]


def test_end_to_end_darija_conversation(db, agent):
    r = agent.respond("c1", "slm")
    assert r.lang == "darija" and "Merhba" in r.text and names(r) == []

    r = agent.respond("c1", "ch7al soum la montre?")
    assert "get_price_and_stock" in names(r) and "6 500 DA" in r.text and "14 pièces en stock" in r.text

    r = agent.respond("c1", "n7eb ncommandi 2")  # product remembered from previous turn
    assert "wilaya" in r.text.lower() and agent.sessions.get("c1").draft.qty == 2

    r = agent.respond("c1", "Oran")
    assert "quote_shipping" in names(r) and "600 DA" in r.text

    r = agent.respond("c1", "Karim Benali")
    assert "telephone" in r.text

    r = agent.respond("c1", "0661 23 45 67")
    assert "3enwan" in r.text

    r = agent.respond("c1", "Cité 500 logements, Es Senia")
    assert names(r)[-1] == "create_cod_order"
    assert "13 600 DA" in r.text and "DZ-1003" in r.text
    assert r.tool_calls[-1].input["items"] == [{"sku": "MON-01", "qty": 2}]
    assert db.one("SELECT status FROM orders WHERE id=3")["status"] == "pending_confirmation"

    r = agent.respond("c1", "iyeh confirmi")
    assert names(r) == ["confirm_order"] and "confirmée" in r.text
    assert db.one("SELECT status FROM orders WHERE id=3")["status"] == "confirmed"

    r = agent.respond("c1", "win wsslet commande?")
    assert names(r) == ["track_shipment"] and "DZ-1003" in r.text and "13 600 DA" in r.text
    assert not any(c.result.get("ok") is False for c in r.tool_calls)


def test_french_conversation_and_reply_language(agent):
    r = agent.respond("f1", "Bonjour")
    assert r.lang == "fr" and "Bienvenue" in r.text
    r = agent.respond("f1", "Quel est le prix des écouteurs ?")
    assert "3 200 DA" in r.text and r.lang == "fr"
    r = agent.respond("f1", "Quel est le prix de livraison pour Sétif ?")
    assert "600 DA" in r.text and "Sétif" in r.text


def test_arabic_conversation(agent):
    r = agent.respond("a1", "السلام عليكم")
    assert r.lang == "ar" and "مرحبا" in r.text
    r = agent.respond("a1", "بشحال الساعة؟")
    assert "6 500 دج" in r.text and "get_price_and_stock" in names(r) and "اختر" not in r.text
    r = agent.respond("a1", "كم التوصيل لوهران")
    assert "600 دج" in r.text and "وهران" in r.text


def test_out_of_stock_product(agent):
    r = agent.respond("o1", "ch7al soum sabat running?")
    assert "rupture" in r.text and "5 400 DA" in r.text
    r = agent.respond("o1", "bghit nakhod")
    assert "rupture" in r.text


def test_invalid_phone_is_rejected_then_accepted(agent):
    for m in ["bghit nakhod lampe", "Alger", "Sofiane"]:
        agent.respond("p1", m)
    r = agent.respond("p1", "0412345678")
    assert "05, 06 wla 07" in r.text and agent.sessions.get("p1").draft.phone is None
    r = agent.respond("p1", "0771234567")
    assert "3enwan" in r.text


def test_tracking_requires_matching_phone(agent):
    r = agent.respond("t1", "win rahi commande DZ-1001")
    assert "telephone" in r.text and r.tool_calls == []
    r = agent.respond("t1", "0661111111")
    assert "ytabe9ch" in r.text
    r = agent.respond("t2", "où est ma commande DZ-1001 ?")
    assert "téléphone" in r.text
    r = agent.respond("t2", "0555123456")
    assert "track_shipment" in names(r) and "hub local" in r.text


def test_escalation_on_complaint_and_on_confusion(db, agent):
    r = agent.respond("h1", "je veux parler à un humain, j'ai un problème avec ma commande")
    assert r.escalated and names(r) == ["escalate_to_human"] and "ESC-1" in r.text
    assert db.one("SELECT COUNT(*) AS n FROM escalations")["n"] == 1
    agent.respond("h2", "zxqv plmk")
    r = agent.respond("h2", "qqqq wwww")
    assert r.escalated


def test_cancel_pending_order(agent):
    for m in ["bghit nakhod lampe", "Blida", "Nadia Kaci", "0551234567", "Rue des Fleurs 12"]:
        r = agent.respond("x1", m)
    assert "DZ-" in r.text
    r = agent.respond("x1", "ma bghitch, annuli")
    assert names(r) == ["cancel_order"] and "tannulat" in r.text


def test_replies_never_contain_unverified_numbers(db):
    agent = OfflineAgent(db)
    msgs = ["slm", "chno 3andkom", "ch7al soum lampe", "livraison l blida ch7al", "wach nkhalas 3and l'istilam"]
    for m in msgs:
        r = agent.respond("g1", m)
        g = PriceStockGuard()
        for c in r.tool_calls:
            g.observe(c.result)
        assert g.check(r.text) == [], m


def test_entity_helpers():
    assert extract_phone("rani 06 61-23 45 67 merci") == "0661234567"
    assert extract_phone("+213 661 23 45 67") == "0661234567"
    assert extract_phone("0412345678") is None
    assert extract_qty("je prends 3 montres") == 3 and extract_qty("bghit zouj") == 2
    assert extract_qty("x4") == 4 and extract_qty("rien") is None
    assert extract_qty("0661234567") is None
