"""Shop tools shared by the Claude agent and the offline agent.

Every tool returns a plain dict: {"ok": True, ...} or {"ok": False, "error": code, "message": text}.
Prices, fees, totals and stock are always read from SQLite; tools never accept a price argument.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from . import tracking
from .db import Database, now_iso, order_ref, parse_order_ref
from .lang import normalize, strip_accents

PHONE_RE = re.compile(r"^0[567]\d{8}$")

# Spellings customers actually use (normalised, no accents) -> canonical wilaya in the shipping table.
WILAYA_ALIASES = {
    "alger": "Alger", "algiers": "Alger", "dzayer": "Alger", "el djazair": "Alger", "الجزائر": "Alger",
    "algerie": "Alger", "alger centre": "Alger", "الجزاير": "Alger",
    "oran": "Oran", "wahran": "Oran", "وهران": "Oran",
    "constantine": "Constantine", "qsentina": "Constantine", "قسنطينه": "Constantine",
    "9sentina": "Constantine", "قسنطينة": "Constantine", "costantine": "Constantine",
    "blida": "Blida", "البليده": "Blida", "بليده": "Blida", "elbolida": "Blida",
    "setif": "Sétif", "سطيف": "Sétif",
    "annaba": "Annaba", "عنابه": "Annaba",
    "tizi ouzou": "Tizi Ouzou", "tizi": "Tizi Ouzou", "تيزي وزو": "Tizi Ouzou",
    "bejaia": "Béjaïa", "bgayet": "Béjaïa", "بجايه": "Béjaïa",
    "batna": "Batna", "باتنه": "Batna",
    "tlemcen": "Tlemcen", "تلمسان": "Tlemcen",
    "ghardaia": "Ghardaïa", "غرداية": "Ghardaïa",
}


# --------------------------------------------------------------------------- pure helpers
def normalize_phone(raw: str) -> str | None:
    """Return a canonical 10-digit Algerian mobile number (05/06/07 + 8 digits) or None."""
    digits = re.sub(r"[\s.\-()]", "", str(raw))
    if digits.startswith("+213"):
        digits = "0" + digits[4:]
    elif digits.startswith("00213"):
        digits = "0" + digits[5:]
    elif digits.startswith("213") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits if PHONE_RE.match(digits) else None


def find_wilaya(text: str) -> str | None:
    """Find a known wilaya inside free text (handles Latin/Arabic/Arabizi spellings)."""
    norm = " " + normalize(text) + " "
    for alias in sorted(WILAYA_ALIASES, key=len, reverse=True):
        a = normalize(alias)
        if f" {a} " in norm:
            return WILAYA_ALIASES[alias]
        # tolerate a leading article/preposition glued on: lwahran, l oran, loran
        if len(a) >= 4 and re.search(rf"(?<!\w)(?:l|el|al|la|a|f|fi|ل|ب|ف|و)?{re.escape(a)}(?!\w)", norm):
            return WILAYA_ALIASES[alias]
    return None


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# --------------------------------------------------------------------------- tools
class ShopTools:
    def __init__(self, db: Database):
        self.db = db

    def _err(self, code: str, message: str, **extra: Any) -> dict:
        return {"ok": False, "error": code, "message": message, **extra}

    # -- catalog ---------------------------------------------------------
    @staticmethod
    def _tokens(text: str) -> list[str]:
        stop = {"de", "du", "des", "la", "le", "les", "un", "une", "l", "d", "a", "pour", "avec", "sans",
                "wach", "kayn", "kayna", "3andkom", "ch", "chحal", "soum", "prix", "ثمن", "سعر", "في", "من"}
        toks = [t[2:] if t.startswith("ال") and len(t) > 4 else t for t in normalize(text).split()]
        return [t for t in toks if len(t) > 1 and t not in stop and not t.isdigit()]

    def _score(self, q_tokens: list[str], product: dict) -> float:
        kw = set(self._tokens(" ".join([product["name_fr"], product["name_ar"], product["keywords"]])))
        score = 0.0
        for t in q_tokens:
            if t in kw:
                score += 1.0
            elif len(t) >= 4:
                best = max((difflib.SequenceMatcher(None, t, k).ratio() for k in kw if len(k) >= 4), default=0)
                if best >= 0.84:
                    score += 0.8
        return score

    def search_products(self, query: str, limit: int = 5) -> dict:
        """Search the catalog by free text (French / Arabic / Darija-Latin). Returns names and prices from DB."""
        q = self._tokens(query)
        rows = self.db.query("SELECT * FROM products")
        scored = sorted(((self._score(q, p), p) for p in rows), key=lambda x: -x[0])
        hits = [(s, p) for s, p in scored if s > 0][:limit]
        if not q:  # empty query = list whole catalog
            hits = [(0.0, p) for p in rows][:limit]
        return {
            "ok": True,
            "count": len(hits),
            "products": [
                {"sku": p["sku"], "name_fr": p["name_fr"], "name_ar": p["name_ar"],
                 "price_dzd": p["price_dzd"], "in_stock": p["stock"] > 0, "match_score": round(s, 2)}
                for s, p in hits
            ],
        }

    def get_price_and_stock(self, sku: str) -> dict:
        p = self.db.one("SELECT * FROM products WHERE sku=?", (str(sku).upper(),))
        if not p:
            return self._err("unknown_product", f"No product with sku {sku!r}. Do not guess a price.")
        return {"ok": True, "sku": p["sku"], "name_fr": p["name_fr"], "name_ar": p["name_ar"],
                "price_dzd": p["price_dzd"], "stock": p["stock"], "in_stock": p["stock"] > 0}

    def quote_shipping(self, wilaya: str) -> dict:
        canon = find_wilaya(wilaya) or next(
            (r["wilaya"] for r in self.db.query("SELECT wilaya FROM shipping_fees")
             if strip_accents(r["wilaya"]).lower() == strip_accents(str(wilaya)).lower().strip()), None)
        row = self.db.one("SELECT * FROM shipping_fees WHERE wilaya=?", (canon,)) if canon else None
        if not row:
            covered = [r["wilaya"] for r in self.db.query("SELECT wilaya FROM shipping_fees ORDER BY wilaya")]
            return self._err("wilaya_not_covered", f"No demo shipping fee for {wilaya!r}.", covered=covered)
        return {"ok": True, "wilaya": row["wilaya"], "fee_dzd": row["fee_dzd"], "eta_days": row["eta_days"],
                "note": "DEMO value, not a real carrier price"}

    # -- orders ----------------------------------------------------------
    def create_cod_order(self, customer_name: str, phone: str, wilaya: str, address: str,
                         items: list[dict]) -> dict:
        """Create a cash-on-delivery order in status pending_confirmation. Prices come from the DB."""
        name = str(customer_name or "").strip()
        if len(name) < 2:
            return self._err("invalid_name", "Customer name is required.")
        norm_phone = normalize_phone(phone)
        if not norm_phone:
            return self._err("invalid_phone",
                             "Phone must be an Algerian mobile: 05/06/07 followed by 8 digits (e.g. 0661234567).")
        if len(str(address or "").strip()) < 5:
            return self._err("invalid_address", "Delivery address is too short.")
        ship = self.quote_shipping(wilaya)
        if not ship["ok"]:
            return ship
        if not items:
            return self._err("empty_order", "At least one item is required.")
        lines, subtotal = [], 0
        for it in items:
            sku, qty = str(it.get("sku", "")).upper(), it.get("qty", 1)
            if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1 or qty > 20:
                return self._err("invalid_quantity", f"Quantity for {sku} must be an integer from 1 to 20.")
            p = self.db.one("SELECT * FROM products WHERE sku=?", (sku,))
            if not p:
                return self._err("unknown_product", f"Unknown sku {sku!r}.")
            if p["stock"] < qty:
                return self._err("insufficient_stock", f"Only {p['stock']} in stock for {sku}.",
                                 sku=sku, stock=p["stock"])
            lines.append((p, qty))
            subtotal += p["price_dzd"] * qty
        existing = self.db.one("SELECT id FROM customers WHERE phone=?", (norm_phone,))
        cid = existing["id"] if existing else self.db.execute(
            "INSERT INTO customers(phone,name) VALUES (?,?)", (norm_phone, name))
        total = subtotal + ship["fee_dzd"]
        oid = self.db.execute(
            "INSERT INTO orders(customer_id,wilaya,address,subtotal_dzd,shipping_fee_dzd,total_dzd,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (cid, ship["wilaya"], str(address).strip(), subtotal, ship["fee_dzd"], total,
             "pending_confirmation", now_iso()))
        for p, qty in lines:
            self.db.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid, p["sku"], qty, p["price_dzd"]))
        return {"ok": True, "order_id": order_ref(oid), "status": "pending_confirmation", "phone": norm_phone,
                "wilaya": ship["wilaya"], "eta_days": ship["eta_days"], "subtotal_dzd": subtotal,
                "shipping_fee_dzd": ship["fee_dzd"], "total_dzd": total, "payment": "cash on delivery",
                "items": [{"sku": p["sku"], "name_fr": p["name_fr"], "name_ar": p["name_ar"], "qty": q,
                           "unit_price_dzd": p["price_dzd"], "line_total_dzd": p["price_dzd"] * q}
                          for p, q in lines]}

    def _load_order(self, order_id: str | int, phone: str | None) -> tuple[dict | None, dict | None]:
        oid = parse_order_ref(order_id)
        if oid is None:
            return None, self._err("invalid_order_id", "Order id looks like DZ-1001.")
        o = self.db.one("SELECT o.*, c.phone, c.name FROM orders o JOIN customers c ON c.id=o.customer_id "
                        "WHERE o.id=?", (oid,))
        if not o:
            return None, self._err("order_not_found", f"No order {order_id}.")
        if phone is None or normalize_phone(phone) != o["phone"]:
            return None, self._err("phone_mismatch", "Phone number does not match this order. "
                                   "Ask the customer for the phone used when ordering.")
        return o, None

    def _items(self, oid: int) -> list[dict]:
        return self.db.query(
            "SELECT i.sku, p.name_fr, p.name_ar, i.qty, i.unit_price_dzd, i.qty*i.unit_price_dzd AS line_total_dzd "
            "FROM order_items i JOIN products p ON p.sku=i.sku WHERE i.order_id=?", (oid,))

    def confirm_order(self, order_id: str, phone: str) -> dict:
        """Customer confirms a pending COD order: re-checks stock, reserves it, creates the shipment."""
        o, err = self._load_order(order_id, phone)
        if err:
            return err
        if o["status"] != "pending_confirmation":
            return self._err("not_pending", f"Order is already {o['status']}.", status=o["status"])
        items = self._items(o["id"])
        for it in items:
            if self.db.one("SELECT stock FROM products WHERE sku=?", (it["sku"],))["stock"] < it["qty"]:
                return self._err("insufficient_stock", f"{it['sku']} is no longer available in that quantity.")
        for it in items:
            self.db.execute("UPDATE products SET stock=stock-? WHERE sku=?", (it["qty"], it["sku"]))
        self.db.execute("UPDATE orders SET status='confirmed', confirmed_at=? WHERE id=?", (now_iso(), o["id"]))
        code = tracking.create_shipment(self.db, o["id"])
        return {"ok": True, "order_id": order_ref(o["id"]), "status": "confirmed", "tracking_code": code,
                "total_dzd": o["total_dzd"], "eta_days": self.quote_shipping(o["wilaya"])["eta_days"]}

    def cancel_order(self, order_id: str, phone: str) -> dict:
        o, err = self._load_order(order_id, phone)
        if err:
            return err
        if o["status"] != "pending_confirmation":
            return self._err("not_cancellable", f"Order is {o['status']}; only a human can cancel it now.")
        self.db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        return {"ok": True, "order_id": order_ref(o["id"]), "status": "cancelled"}

    def get_order_status(self, order_id: str, phone: str) -> dict:
        o, err = self._load_order(order_id, phone)
        if err:
            return err
        return {"ok": True, "order_id": order_ref(o["id"]), "status": o["status"], "wilaya": o["wilaya"],
                "subtotal_dzd": o["subtotal_dzd"], "shipping_fee_dzd": o["shipping_fee_dzd"],
                "total_dzd": o["total_dzd"], "items": self._items(o["id"]),
                "tracking_code": o["tracking_code"], "created_at": o["created_at"]}

    def track_shipment(self, order_id: str, phone: str) -> dict:
        o, err = self._load_order(order_id, phone)
        if err:
            return err
        if not o["tracking_code"]:
            return self._err("no_shipment", f"Order is {o['status']}; no shipment exists yet.", status=o["status"])
        ev = tracking.events(self.db, o["tracking_code"])
        return {"ok": True, "order_id": order_ref(o["id"]), "tracking_code": o["tracking_code"],
                "current_stage": ev[-1]["stage"], "location": ev[-1]["location"], "events": ev,
                "total_dzd": o["total_dzd"], "note": "Mock tracking service (demo)"}

    def escalate_to_human(self, reason: str, session_id: str = "unknown", summary: str = "") -> dict:
        if not str(reason or "").strip():
            return self._err("reason_required", "A reason is required to escalate.")
        eid = self.db.execute("INSERT INTO escalations(session_id,reason,summary,created_at) VALUES (?,?,?,?)",
                              (session_id, str(reason).strip(), summary, now_iso()))
        return {"ok": True, "ticket": f"ESC-{eid}", "message": "A human agent will contact the customer."}

    # -- dispatch --------------------------------------------------------
    def call(self, name: str, args: dict, session_id: str = "unknown") -> dict:
        fn = {
            "search_products": self.search_products, "get_price_and_stock": self.get_price_and_stock,
            "quote_shipping": self.quote_shipping, "create_cod_order": self.create_cod_order,
            "confirm_order": self.confirm_order, "cancel_order": self.cancel_order,
            "get_order_status": self.get_order_status, "track_shipment": self.track_shipment,
            "escalate_to_human": lambda **kw: self.escalate_to_human(session_id=session_id, **kw),
        }.get(name)
        if fn is None:
            return self._err("unknown_tool", f"No tool named {name!r}.")
        try:
            return fn(**args)
        except TypeError as e:  # wrong/missing arguments from the model
            return self._err("bad_arguments", str(e))


def _s(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOL_SCHEMAS = [
    {"name": "search_products", "description": "Search the shop catalog by free text (French, Arabic or Darija "
     "in Latin script). Returns matching products with DB prices. Empty query lists the catalog.",
     "input_schema": _s({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"])},
    {"name": "get_price_and_stock", "description": "Get the exact price (DZD) and stock of one product by sku. "
     "The only valid source of prices and stock.",
     "input_schema": _s({"sku": {"type": "string"}}, ["sku"])},
    {"name": "quote_shipping", "description": "Get the (demo) shipping fee and delivery time for a wilaya.",
     "input_schema": _s({"wilaya": {"type": "string"}}, ["wilaya"])},
    {"name": "create_cod_order", "description": "Create a cash-on-delivery order (status pending_confirmation). "
     "Needs the customer's real name, an Algerian mobile (05/06/07 + 8 digits), wilaya, address and items. "
     "Never pass prices; they are read from the DB.",
     "input_schema": _s({
         "customer_name": {"type": "string"}, "phone": {"type": "string"}, "wilaya": {"type": "string"},
         "address": {"type": "string"},
         "items": {"type": "array", "items": _s({"sku": {"type": "string"}, "qty": {"type": "integer"}},
                                                ["sku", "qty"])}},
         ["customer_name", "phone", "wilaya", "address", "items"])},
    {"name": "confirm_order", "description": "Confirm a pending order after the customer explicitly agrees "
     "to the total. Reserves stock and creates the shipment.",
     "input_schema": _s({"order_id": {"type": "string"}, "phone": {"type": "string"}}, ["order_id", "phone"])},
    {"name": "cancel_order", "description": "Cancel an order that is still pending confirmation.",
     "input_schema": _s({"order_id": {"type": "string"}, "phone": {"type": "string"}}, ["order_id", "phone"])},
    {"name": "get_order_status", "description": "Status, totals and items of an order. Requires the order id "
     "and the phone number used for the order.",
     "input_schema": _s({"order_id": {"type": "string"}, "phone": {"type": "string"}}, ["order_id", "phone"])},
    {"name": "track_shipment", "description": "Delivery tracking events for a confirmed order (mock carrier).",
     "input_schema": _s({"order_id": {"type": "string"}, "phone": {"type": "string"}}, ["order_id", "phone"])},
    {"name": "escalate_to_human", "description": "Hand the conversation to a human agent. Use for complaints, "
     "refunds, returns, anger, requests for a person, or anything outside shop policy. Give a clear reason.",
     "input_schema": _s({"reason": {"type": "string"}, "summary": {"type": "string"}}, ["reason"])},
]
