"""FastAPI app: /chat, web chat UI at /, admin page at /admin."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import tracking
from .claude_agent import build_agent
from .db import Database, order_ref
from .tools import ShopTools

STATIC = Path(__file__).parent / "static"


class ChatIn(BaseModel):
    customer_id: str = Field(default="web", max_length=64)
    message: str = Field(min_length=1, max_length=2000)


def create_app(db_path: str | None = None, force_offline: bool = False) -> FastAPI:
    db = Database(db_path or os.environ.get("DZSHOP_DB", "dzshop.sqlite3"))
    agent = build_agent(db, force_offline=force_offline)
    lock = threading.Lock()
    app = FastAPI(title="dzshop-agent", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": agent.mode}

    @app.post("/chat")
    def chat(body: ChatIn):
        with lock:
            r = agent.respond(body.customer_id, body.message)
        return {"reply": r.text, "language": r.lang, "mode": r.mode, "escalated": r.escalated,
                "tool_calls": [{"name": c.name, "input": c.input, "ok": c.result.get("ok")} for c in r.tool_calls]}

    @app.get("/api/orders")
    def orders():
        rows = db.query(
            "SELECT o.id, o.status, o.wilaya, o.total_dzd, o.created_at, o.confirmed_at, o.tracking_code, "
            "c.name, c.phone FROM orders o JOIN customers c ON c.id=o.customer_id ORDER BY o.id DESC")
        for r in rows:
            r["order_id"] = order_ref(r.pop("id"))
            r["stage"] = tracking.current_stage(db, r["tracking_code"]) if r["tracking_code"] else None
        return rows

    @app.get("/api/escalations")
    def escalations():
        return db.query("SELECT * FROM escalations ORDER BY id DESC")

    @app.post("/api/orders/{order_id}/advance")
    def advance(order_id: str):
        """Demo helper: move the mock shipment of an order to its next stage."""
        o = db.one("SELECT tracking_code FROM orders WHERE id=?", (int(order_id.split("-")[-1]) - 1000,))
        if not o or not o["tracking_code"]:
            raise HTTPException(404, "no shipment for this order")
        return {"stage": tracking.advance(db, o["tracking_code"])}

    @app.get("/api/products")
    def products():
        return ShopTools(db).search_products("", 50)["products"]

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/admin")
    def admin():
        return FileResponse(STATIC / "admin.html")

    return app

