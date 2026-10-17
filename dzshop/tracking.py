"""Mock delivery-tracking service. No real carrier is contacted; progress is simulated."""

from __future__ import annotations

import random

from .db import STAGES, Database, now_iso

_LOCATIONS = {
    "label_created": "Entrepôt démo - Alger",
    "picked_up": "Entrepôt démo - Alger",
    "in_transit": "Centre de tri démo - Alger",
    "at_local_hub": "Hub démo - {wilaya}",
    "out_for_delivery": "Livreur démo - {wilaya}",
    "delivered": "Remise au client - {wilaya}",
}


def new_tracking_code(rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    return f"DZT{rng.randint(100000, 999999)}"


def _add_event(db: Database, code: str, stage: str, wilaya: str) -> None:
    db.execute(
        "INSERT INTO shipment_events(tracking_code,stage,location,ts) VALUES (?,?,?,?)",
        (code, stage, _LOCATIONS[stage].format(wilaya=wilaya), now_iso()),
    )


def create_shipment(db: Database, order_id: int) -> str:
    order = db.one("SELECT wilaya FROM orders WHERE id=?", (order_id,))
    code = new_tracking_code()
    while db.one("SELECT 1 FROM orders WHERE tracking_code=?", (code,)):
        code = new_tracking_code()
    db.execute("UPDATE orders SET tracking_code=? WHERE id=?", (code, order_id))
    _add_event(db, code, "label_created", order["wilaya"])
    return code


def events(db: Database, code: str) -> list[dict]:
    return db.query("SELECT stage, location, ts FROM shipment_events WHERE tracking_code=? ORDER BY id", (code,))


def current_stage(db: Database, code: str) -> str | None:
    ev = events(db, code)
    return ev[-1]["stage"] if ev else None


def advance(db: Database, code: str) -> str | None:
    """Move a shipment to its next stage (simulation). Returns the new stage, or None if finished."""
    order = db.one("SELECT id, wilaya FROM orders WHERE tracking_code=?", (code,))
    stage = current_stage(db, code)
    if order is None or stage is None or stage == STAGES[-1]:
        return None
    nxt = STAGES[STAGES.index(stage) + 1]
    _add_event(db, code, nxt, order["wilaya"])
    status = "delivered" if nxt == "delivered" else "shipped" if nxt != "label_created" else "confirmed"
    db.execute("UPDATE orders SET status=? WHERE id=?", (status, order["id"]))
    return nxt
