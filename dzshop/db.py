"""SQLite mock backend for a DEMO shop: catalog, customers, orders, shipping fees, shipments.

Everything here is invented sample data. Prices and shipping fees are demo values, not real
carrier or market prices.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

SHOP_NAME = "Boutique Démo Dzair (DEMO)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY, name_fr TEXT NOT NULL, name_ar TEXT NOT NULL,
  keywords TEXT NOT NULL, price_dzd INTEGER NOT NULL, stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shipping_fees (
  wilaya TEXT PRIMARY KEY, fee_dzd INTEGER NOT NULL, eta_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL REFERENCES customers(id),
  wilaya TEXT NOT NULL, address TEXT NOT NULL, subtotal_dzd INTEGER NOT NULL,
  shipping_fee_dzd INTEGER NOT NULL, total_dzd INTEGER NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, confirmed_at TEXT,
  tracking_code TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
  order_id INTEGER NOT NULL REFERENCES orders(id), sku TEXT NOT NULL REFERENCES products(sku),
  qty INTEGER NOT NULL, unit_price_dzd INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS shipment_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_code TEXT NOT NULL,
  stage TEXT NOT NULL, location TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS escalations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, reason TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
"""

# (sku, name_fr, name_ar, keywords (fr / ar / darija-latin), price_dzd, stock)
PRODUCTS = [
    ("MON-01", "Montre connectée Nova", "ساعة ذكية نوفا",
     "montre watch smartwatch mountra mont ra ساعة ساعه connectee connectée nova", 6500, 14),
    ("ECO-02", "Écouteurs sans fil Pulse", "سماعات لاسلكية بولس",
     "ecouteurs ecouteur oreillette airpods casque ecouteur sans fil سماعات سماعه ecouteurs pulse bluetooth", 3200, 30),
    ("SAC-03", "Sac à dos urbain", "حقيبة ظهر عصرية",
     "sac dos cartable backpack sakados sac a dos حقيبة شنطة محفظة urbain", 2800, 9),
    ("CHA-04", "Chaussures running Atlas", "حذاء رياضي أطلس",
     "chaussures chaussure sabat sbat basket baskets running sport حذاء صباط sabbat atlas", 5400, 0),
    ("PWB-05", "Powerbank 20000 mAh", "باور بانك 20000",
     "powerbank power bank batterie chargeur externe باور بانك شاحن powerbank", 3900, 22),
    ("LAM-06", "Lampe LED de bureau", "مصباح مكتب LED",
     "lampe lamp led bureau lumiere eclairage مصباح لمبة lampe", 1900, 17),
    ("TAP-07", "Tapis de yoga", "سجادة يوغا",
     "tapis yoga sport fitness tapis de yoga سجادة يوغا tapis", 1500, 25),
    ("COQ-08", "Coque silicone universelle", "غطاء سيليكون",
     "coque protection telephone portable silicone coque غطاء كوك", 700, 60),
]

# Demo shipping fees (NOT real carrier prices). (wilaya, fee_dzd, eta_days)
SHIPPING = [
    ("Alger", 400, 1), ("Blida", 500, 2), ("Oran", 600, 3), ("Constantine", 600, 3),
    ("Sétif", 600, 3), ("Annaba", 650, 3), ("Tizi Ouzou", 550, 2), ("Béjaïa", 600, 3),
    ("Batna", 650, 3), ("Tlemcen", 700, 4), ("Ghardaïa", 900, 5),
]

STAGES = ["label_created", "picked_up", "in_transit", "at_local_hub", "out_for_delivery", "delivered"]
STATUSES = ["pending_confirmation", "confirmed", "shipped", "delivered", "cancelled"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: str = ":memory:", seed: bool = True):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        if seed and not self.query("SELECT 1 FROM products LIMIT 1"):
            self._seed()

    # -- helpers ---------------------------------------------------------
    def query(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def execute(self, sql: str, args: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    # -- seed ------------------------------------------------------------
    def _seed(self) -> None:
        with self.lock:
            self.conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", PRODUCTS)
            self.conn.executemany("INSERT INTO shipping_fees VALUES (?,?,?)", SHIPPING)
            self.conn.commit()
        base = datetime.now(timezone.utc).replace(microsecond=0)
        # Demo order 1001: already shipped to Oran, phone 0555123456.
        cid = self.execute("INSERT INTO customers(phone,name) VALUES (?,?)", ("0555123456", "Samir Demo"))
        oid = self.execute(
            "INSERT INTO orders(customer_id,wilaya,address,subtotal_dzd,shipping_fee_dzd,total_dzd,status,"
            "created_at,confirmed_at,tracking_code) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, "Oran", "Cité Demo 12, Oran", 3200, 600, 3800, "shipped",
             (base - timedelta(days=2)).isoformat(), (base - timedelta(days=2, hours=-1)).isoformat(), "DZT100100"))
        self.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid, "ECO-02", 1, 3200))
        for i, (stage, loc) in enumerate([
            ("label_created", "Entrepôt démo - Alger"), ("picked_up", "Entrepôt démo - Alger"),
            ("in_transit", "Centre de tri démo - Alger"), ("at_local_hub", "Hub démo - Oran")]):
            self.execute("INSERT INTO shipment_events(tracking_code,stage,location,ts) VALUES (?,?,?,?)",
                         ("DZT100100", stage, loc, (base - timedelta(days=2, hours=-i * 8)).isoformat()))
        # Demo order 1002: waiting for COD confirmation.
        cid2 = self.execute("INSERT INTO customers(phone,name) VALUES (?,?)", ("0661000000", "Amina Demo"))
        oid2 = self.execute(
            "INSERT INTO orders(customer_id,wilaya,address,subtotal_dzd,shipping_fee_dzd,total_dzd,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (cid2, "Blida", "Rue Demo 4, Blida", 1500, 500, 2000, "pending_confirmation", base.isoformat()))
        self.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid2, "TAP-07", 1, 1500))


def order_ref(order_id: int) -> str:
    """Public order reference, e.g. DZ-1001."""
    return f"DZ-{1000 + order_id}"


def parse_order_ref(ref: str | int) -> int | None:
    """DZ-1001 / dz1001 / #1001 / 1001 -> internal id (1)."""
    import re
    m = re.search(r"(\d{4,})", str(ref))
    if not m:
        return None
    n = int(m.group(1)) - 1000
    return n if n > 0 else None
