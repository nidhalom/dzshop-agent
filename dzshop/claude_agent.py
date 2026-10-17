"""Claude-backed agent: official `anthropic` SDK, manual tool-use loop, per-customer memory."""

from __future__ import annotations

import os

from .db import SHOP_NAME, Database
from .guard import PriceStockGuard
from .lang import detect_language
from .session import AgentReply, SessionStore, ToolCall
from .tools import TOOL_SCHEMAS, ShopTools

MODEL = "claude-opus-5-5"
MAX_TURNS = 8

SYSTEM_PROMPT = f"""You are the customer-service and order agent of "{SHOP_NAME}", a small Algerian online shop \
that sells on Facebook/Instagram and delivers cash-on-delivery (COD). This is a DEMO shop with invented data.

Language: customers write Darija (often in Latin script with numerals: 3=ع, 7=ح, 9=ق, 5=خ), Arabic or French. \
Always reply in the language and script of the customer's last message (Darija-Latin -> Darija in Latin script; \
Arabic script -> Arabic; French -> French). Keep replies short, warm and chat-like.

Hard rules:
1. Prices, shipping fees, totals and stock come ONLY from tool results. Never invent, estimate or round them. \
If a tool has no answer, say you will check or escalate.
2. To take an order you need: product(s) and quantity, wilaya, full name, an Algerian mobile number \
(05/06/07 + 8 digits) and a delivery address. Ask for missing pieces one or two at a time. Quote the shipping fee \
with quote_shipping, then call create_cod_order, read the total back, and ask the customer to confirm. \
Call confirm_order ONLY after the customer clearly agrees to the total.
3. Payment is cash on delivery only. Shipping fees shown are demo values.
4. For order status or tracking, ask for the order id (like DZ-1001) and the phone used when ordering, then use \
get_order_status / track_shipment. Never reveal an order whose phone does not match.
5. Use escalate_to_human (with a clear reason) for complaints, refunds, returns, anger, requests for a person, \
cancellations after confirmation, or anything outside this policy. Tell the customer a human will contact them.
6. Do not discuss anything unrelated to the shop."""

SAFE_FALLBACK = {
    "darija": "Sma7 lina, bach nkoun mt2ekked rani nwasselek l wa7ed mn l'équipe.",
    "ar": "عذرا، للتأكد من المعلومات سأحول محادثتك إلى أحد أفراد الفريق.",
    "fr": "Désolé, pour être sûr de l'information je transmets votre demande à un membre de l'équipe.",
}


def _block_get(block, key, default=None):
    return block.get(key, default) if isinstance(block, dict) else getattr(block, key, default)


class ClaudeAgent:
    mode = "claude"

    def __init__(self, db: Database, sessions: SessionStore | None = None, client=None, model: str = MODEL):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.client, self.model = client, model
        self.db = db
        self.tools = ShopTools(db)
        self.sessions = sessions or SessionStore()
        self.guard = PriceStockGuard()

    def respond(self, customer_id: str, text: str) -> AgentReply:
        s = self.sessions.get(customer_id)
        det = detect_language(text)
        if det.lang != "und":
            s.lang = det.lang
        self.guard.reset()
        calls: list[ToolCall] = []
        escalated = False
        s.transcript.append(("customer", text))
        s.messages.append({"role": "user", "content": text})

        reply = ""
        for _ in range(MAX_TURNS):
            response = self.client.messages.create(
                model=self.model, max_tokens=16000, system=SYSTEM_PROMPT, tools=TOOL_SCHEMAS, messages=s.messages)
            if response.stop_reason == "refusal":
                reply = SAFE_FALLBACK.get(s.lang, SAFE_FALLBACK["fr"])
                break
            s.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                reply = "".join(_block_get(b, "text", "") for b in response.content
                                if _block_get(b, "type") == "text").strip()
                break
            results = []
            for b in response.content:
                if _block_get(b, "type") != "tool_use":
                    continue
                name, args = _block_get(b, "name"), _block_get(b, "input") or {}
                res = self.tools.call(name, dict(args), session_id=customer_id)
                self.guard.observe(res)
                calls.append(ToolCall(name, dict(args), res))
                if name == "escalate_to_human" and res.get("ok"):
                    escalated = True
                block = {"type": "tool_result", "tool_use_id": _block_get(b, "id"), "content": str(res)}
                if not res.get("ok"):
                    block["is_error"] = True
                results.append(block)
            s.messages.append({"role": "user", "content": results})
        else:
            reply = SAFE_FALLBACK.get(s.lang, SAFE_FALLBACK["fr"])

        problems = self.guard.check(reply)
        if problems:  # the model quoted a number no tool returned: do not send it
            res = self.tools.escalate_to_human(f"price guard blocked reply: {problems}", customer_id, reply[:300])
            calls.append(ToolCall("escalate_to_human", {"reason": "price guard"}, res))
            reply, escalated = SAFE_FALLBACK.get(s.lang, SAFE_FALLBACK["fr"]), True
        s.transcript.append(("agent", reply))
        return AgentReply(reply, s.lang, calls, escalated, self.mode)


def build_agent(db: Database, force_offline: bool = False):
    """Claude agent when ANTHROPIC_API_KEY is set, otherwise the offline rule-based agent."""
    if not force_offline and os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeAgent(db)
    from .offline import OfflineAgent
    return OfflineAgent(db)
