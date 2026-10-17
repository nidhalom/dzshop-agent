"""Offline agent: rule-based intent routing + slot filling that calls the SAME tools as the Claude agent.

No network, no API key. Replies come from `templates.py`, which only interpolates tool results.
"""

from __future__ import annotations

import re

from .db import Database
from .guard import PriceStockGuard
from .intents import classify
from .lang import detect_language, normalize
from .session import AgentReply, Draft, Session, SessionStore, ToolCall
from .templates import STAGE_LABELS, STATUS_LABELS, render, wname
from .tools import ShopTools, find_wilaya, money, normalize_phone

_PHONE_RE = re.compile(r"(?<!\d)(?:\+213|00213|0)[567]\d{8}(?!\d)")
_ORDER_RE = re.compile(r"(?:\bdz[-\s]?|#)(\d{4,})", re.IGNORECASE)
_YES = {"oui", "iyeh", "ih", "wah", "ok", "okay", "d accord", "yes", "نعم", "ايه", "واه", "موافق", "اكد", "confirmi"}
_NO = {"non", "la", "no", "ma bghitch", "لا", "annuli", "batel"}
_QTY_WORDS = {"zouj": 2, "deux": 2, "ثنين": 2, "اثنين": 2, "زوج": 2, "thnin": 2, "tnin": 2,
              "wahed": 1, "waحed": 1, "un": 1, "une": 1, "واحد": 1, "tlata": 3, "trois": 3, "ثلاثه": 3}
_NAME_PREFIX = re.compile(
    r"^(?:smiti|smiyti|ismi|smitek|je m appelle|je suis|mon nom est|mon nom c est|c est|اسمي|انا|أنا)\s+", re.IGNORECASE)


def extract_phone(text: str) -> str | None:
    collapsed = re.sub(r"(?<=\d)[\s.\-](?=\d)", "", text)
    m = _PHONE_RE.search(collapsed)
    return normalize_phone(m.group(0)) if m else None


def extract_order_ref(text: str) -> str | None:
    m = _ORDER_RE.search(text)
    return f"DZ-{m.group(1)}" if m else None


def extract_qty(text: str) -> int | None:
    t = re.sub(r"(?<=\d)[\s.\-](?=\d)", "", text)
    t = _PHONE_RE.sub(" ", t)
    t = _ORDER_RE.sub(" ", t)
    low = t.lower()
    m = re.search(r"\bx\s?(\d{1,2})\b", low) or re.search(r"\b(\d{1,2})\s?(?:x|pcs|pc|pi[eè]ces?|pieces?|قطع|حبات)", low)
    if m:
        return max(1, min(20, int(m.group(1))))
    for tok in normalize(t).split():
        if tok in _QTY_WORDS:
            return _QTY_WORDS[tok]
    m = re.search(r"(?<![\d\w])([1-9])(?![\d\w])", low)
    return int(m.group(1)) if m else None


class OfflineAgent:
    mode = "offline"

    def __init__(self, db: Database, sessions: SessionStore | None = None):
        self.db = db
        self.tools = ShopTools(db)
        self.sessions = sessions or SessionStore()
        self.guard = PriceStockGuard()

    # ------------------------------------------------------------------ plumbing
    def _call(self, s: Session, calls: list[ToolCall], name: str, **kw) -> dict:
        res = self.tools.call(name, kw, session_id=s.customer_id)
        self.guard.observe(res)
        calls.append(ToolCall(name, kw, res))
        return res

    @staticmethod
    def _pname(p: dict, lang: str) -> str:
        return p["name_ar"] if lang == "ar" else p["name_fr"]

    def _catalog_lines(self, s: Session, calls: list[ToolCall]) -> str:
        res = self._call(s, calls, "search_products", query="", limit=20)
        return "\n".join(f"- {self._pname(p, s.lang)}: {money(p['price_dzd'])} " + ("دج" if s.lang == "ar" else "DA")
                         for p in res["products"])

    def _resolve_product(self, s: Session, calls: list[ToolCall], text: str) -> tuple[str | None, list[dict]]:
        """Return (sku, candidates). sku is None when nothing matched or the match is ambiguous."""
        res = self._call(s, calls, "search_products", query=text, limit=4)
        hits = res["products"]
        if not hits:
            return None, []
        if len(hits) == 1 or hits[0]["match_score"] > hits[1]["match_score"]:
            return hits[0]["sku"], hits
        top = hits[0]["match_score"]
        return None, [h for h in hits if h["match_score"] == top]

    def _escalate(self, s: Session, calls: list[ToolCall], reason: str) -> tuple[str, bool]:
        recent = " | ".join(f"{r}: {t}" for r, t in s.transcript[-6:])
        res = self._call(s, calls, "escalate_to_human", reason=reason, summary=recent)
        return render("escalate", s.lang, ticket=res["ticket"]), True

    # ------------------------------------------------------------------ public API
    def respond(self, customer_id: str, text: str) -> AgentReply:
        s = self.sessions.get(customer_id)
        det = detect_language(text)
        if det.lang != "und":
            s.lang = det.lang
        self.guard.reset()
        calls: list[ToolCall] = []
        s.transcript.append(("customer", text))
        out, escalated = self._route(s, calls, text)
        problems = self.guard.check(out)
        if problems:  # should never happen with templates, but never ship an unverified number
            out, escalated = self._escalate(s, calls, f"price guard blocked reply: {problems}")
        s.transcript.append(("agent", out))
        return AgentReply(out, s.lang, calls, escalated, self.mode)

    # ------------------------------------------------------------------ routing
    def _route(self, s: Session, calls: list[ToolCall], text: str) -> tuple[str, bool]:
        lang, norm = s.lang, normalize(text)
        intent, conf = classify(text)
        phone, oref, wil = extract_phone(text), extract_order_ref(text), find_wilaya(text)

        if intent == "human" and conf >= 0.45:
            s.draft = Draft()
            return self._escalate(s, calls, f"customer asked for a human / complaint: {text[:120]}")

        if s.draft.active:
            return self._fill_draft(s, calls, text, intent, conf, phone, wil), False

        if s.pending_order and (intent == "confirm" and conf >= 0.4 or norm in _YES):
            return self._confirm(s, calls), False
        if s.pending_order and (intent == "cancel" and conf >= 0.4 or norm in _NO):
            res = self._call(s, calls, "cancel_order", order_id=s.pending_order, phone=s.phone)
            if res["ok"]:
                s.pending_order = None
                return render("cancelled", lang, order_id=res["order_id"]), False

        if phone and not oref and s.last_order and s.phone is None and (intent in ("track", "unknown") or conf < 0.5):
            return self._track(s, calls, s.last_order, phone), False

        s.unknown_streak = 0 if intent != "unknown" and conf >= 0.3 else s.unknown_streak
        if conf < 0.3:
            intent = "unknown"

        if intent == "greeting":
            return render("greet", lang), False
        if intent == "catalog":
            return render("catalog", lang, lines=self._catalog_lines(s, calls)), False
        if intent == "price":
            return self._price(s, calls, text), False
        if intent == "shipping":
            return self._shipping(s, calls, wil), False
        if intent == "order":
            s.draft = Draft(active=True, qty=extract_qty(text) or 1, wilaya=wil, phone=phone)
            sku, cands = self._resolve_product(s, calls, text)
            s.draft.sku = sku or (s.last_sku if not cands else None)
            if not s.draft.sku and not cands:
                cands = []
            return self._advance(s, calls, "", cands), False
        if intent == "track":
            return self._track(s, calls, oref or s.last_order, phone or s.phone), False
        if intent == "payment":
            return render("payment", lang), False
        if intent == "thanks":
            return render("thanks", lang), False
        if intent == "cancel":
            return render("draft_cancelled", lang), False
        if intent == "confirm":
            return render("confirm_none", lang), False

        s.unknown_streak += 1
        if s.unknown_streak >= 2:
            s.unknown_streak = 0
            return self._escalate(s, calls, f"could not understand the customer twice: {text[:120]}")
        return render("unknown", lang), False

    # ------------------------------------------------------------------ intents
    def _price(self, s: Session, calls: list[ToolCall], text: str) -> str:
        sku, cands = self._resolve_product(s, calls, text)
        sku = sku or (s.last_sku if not cands else None)
        if not sku:
            lines = "\n".join(f"- {self._pname(p, s.lang)}" for p in cands) if cands else self._catalog_lines(s, calls)
            return render("which_product", s.lang, lines=lines)
        s.last_sku = sku
        p = self._call(s, calls, "get_price_and_stock", sku=sku)
        key = "price_in" if p["in_stock"] else "price_out"
        return render(key, s.lang, name=p["name_fr"], name_ar=p["name_ar"], price=money(p["price_dzd"]), stock=p["stock"])

    def _shipping(self, s: Session, calls: list[ToolCall], wil: str | None) -> str:
        if not wil:
            return render("ship_ask", s.lang)
        q = self._call(s, calls, "quote_shipping", wilaya=wil)
        return render("ship_quote", s.lang, wilaya=wname(q["wilaya"], s.lang), fee=money(q["fee_dzd"]), eta=q["eta_days"])

    def _confirm(self, s: Session, calls: list[ToolCall]) -> str:
        res = self._call(s, calls, "confirm_order", order_id=s.pending_order, phone=s.phone)
        if not res["ok"]:
            return render("stock_fail", s.lang, error=res["message"])
        s.pending_order = None
        return render("confirmed", s.lang, order_id=res["order_id"], total=money(res["total_dzd"]),
                      code=res["tracking_code"], eta=res["eta_days"])

    def _track(self, s: Session, calls: list[ToolCall], oref: str | None, phone: str | None) -> str:
        lang = s.lang
        if not oref:
            return render("need_order_id", lang)
        s.last_order = oref
        if not phone:
            return render("need_phone", lang, order_id=oref)
        res = self._call(s, calls, "track_shipment", order_id=oref, phone=phone)
        if res["ok"]:
            s.phone = phone
            return render("track", lang, order_id=res["order_id"], stage=STAGE_LABELS[res["current_stage"]][lang],
                          location=res["location"], total=money(res["total_dzd"]), code=res["tracking_code"])
        if res["error"] == "no_shipment":
            st = self._call(s, calls, "get_order_status", order_id=oref, phone=phone)
            s.phone = phone
            return render("status_noship", lang, order_id=st["order_id"], status=STATUS_LABELS[st["status"]][lang],
                          total=money(st["total_dzd"]))
        if res["error"] == "phone_mismatch":
            return render("phone_mismatch", lang)
        return render("order_not_found", lang)

    # ------------------------------------------------------------------ order slot filling
    def _fill_draft(self, s: Session, calls: list[ToolCall], text: str, intent: str, conf: float,
                    phone: str | None, wil: str | None) -> str:
        d, lang, norm = s.draft, s.lang, normalize(text)
        if (intent == "cancel" and conf >= 0.5) or norm in _NO:
            s.draft = Draft()
            return render("draft_cancelled", lang)
        question = intent in ("price", "shipping", "payment", "catalog") and conf >= 0.6 \
            and not (d.awaiting == "wilaya" and wil) and not (d.awaiting == "phone" and phone)
        if question and d.awaiting != "product":
            if intent == "price":
                head = self._price(s, calls, text)
            elif intent == "shipping":
                head = self._shipping(s, calls, wil)
            elif intent == "payment":
                head = render("payment", lang)
            else:
                head = render("catalog", lang, lines=self._catalog_lines(s, calls))
            return head + "\n" + self._advance(s, calls, "", [])
        prefix, cands = "", []
        if phone:
            d.phone = phone
        if d.awaiting == "product" or not d.sku:
            sku, cands = self._resolve_product(s, calls, text)
            if sku:
                d.sku, d.awaiting, cands = sku, None, []
        if wil and not d.wilaya:
            d.wilaya = wil
        if d.awaiting == "wilaya" and not d.wilaya and not wil:
            q = self._call(s, calls, "quote_shipping", wilaya=text)
            if not q["ok"]:
                return render("wilaya_unknown", lang, covered=", ".join(q["covered"]))
        if d.awaiting == "name" and not d.name:
            cleaned = _NAME_PREFIX.sub("", text.strip().replace("'", " "), count=1).strip(" .,!")
            if len(cleaned) >= 2 and not re.search(r"\d|\?", cleaned) and len(cleaned.split()) <= 5:
                d.name = cleaned.title()
        if d.awaiting == "address" and not d.address and len(text.strip()) >= 5 and not phone:
            d.address = text.strip()
        if d.awaiting == "phone" and not d.phone and re.search(r"\d{4,}", text):
            return render("bad_phone", lang)
        return self._advance(s, calls, prefix, cands)

    def _advance(self, s: Session, calls: list[ToolCall], prefix: str, cands: list[dict]) -> str:
        d, lang = s.draft, s.lang
        if not d.sku:
            d.awaiting = "product"
            lines = "\n".join(f"- {self._pname(p, lang)}" for p in cands) if cands else self._catalog_lines(s, calls)
            return render("which_product", lang, lines=lines)
        p = self._call(s, calls, "get_price_and_stock", sku=d.sku)
        if not p["in_stock"]:
            s.draft = Draft()
            return render("price_out", lang, name=p["name_fr"], name_ar=p["name_ar"], price=money(p["price_dzd"]))
        s.last_sku = d.sku
        item = f"{d.qty} × {self._pname(p, lang)}"
        if not d.wilaya:
            d.awaiting = "wilaya"
            return render("ask_wilaya", lang, item=item)
        if not d.name:
            d.awaiting = "name"
            q = self._call(s, calls, "quote_shipping", wilaya=d.wilaya)
            ship = render("ship_quote", lang, wilaya=wname(q["wilaya"], lang), fee=money(q["fee_dzd"]), eta=q["eta_days"])
            return render("ask_name", lang, ship=ship)
        if not d.phone:
            d.awaiting = "phone"
            return render("ask_phone", lang, name=d.name.split()[0])
        if not d.address:
            d.awaiting = "address"
            return render("ask_address", lang)
        res = self._call(s, calls, "create_cod_order", customer_name=d.name, phone=d.phone, wilaya=d.wilaya,
                         address=d.address, items=[{"sku": d.sku, "qty": d.qty}])
        if not res["ok"]:
            if res["error"] == "invalid_phone":
                d.phone, d.awaiting = None, "phone"
                return render("bad_phone", lang)
            if res["error"] == "invalid_address":
                d.address, d.awaiting = None, "address"
                return render("ask_address", lang)
            s.draft = Draft()
            return render("stock_fail", lang, error=res["message"])
        s.phone, s.pending_order, s.last_order = res["phone"], res["order_id"], res["order_id"]
        s.draft = Draft()
        cur = "دج" if lang == "ar" else "DA"
        lines = "\n".join(f"- {i['qty']} × {self._pname(i, lang)} = {money(i['line_total_dzd'])} {cur}"
                          for i in res["items"])
        return render("order_summary", lang, order_id=res["order_id"], lines=lines, wilaya=wname(res["wilaya"], lang),
                      fee=money(res["shipping_fee_dzd"]), total=money(res["total_dzd"]))
