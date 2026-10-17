"""Claude agent loop tested with a scripted fake client (no network)."""
from types import SimpleNamespace as NS

from dzshop.claude_agent import SYSTEM_PROMPT, ClaudeAgent


def text(t):
    return NS(type="text", text=t)


def tool_use(i, name, **inp):
    return NS(type="tool_use", id=i, name=name, input=inp)


class FakeClient:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append({"model": kw["model"], "n": len(kw["messages"]), "tools": kw["tools"]})
        return self.responses.pop(0)


def test_manual_tool_loop(db):
    fake = FakeClient([
        NS(stop_reason="tool_use", content=[text("..."), tool_use("t1", "search_products", query="montre")]),
        NS(stop_reason="tool_use", content=[tool_use("t2", "get_price_and_stock", sku="MON-01")]),
        NS(stop_reason="end_turn", content=[text("Soum la montre: 6 500 DA")]),
    ])
    agent = ClaudeAgent(db, client=fake)
    r = agent.respond("k1", "ch7al soum la montre?")
    assert r.text == "Soum la montre: 6 500 DA" and r.mode == "claude" and not r.escalated
    assert [c.name for c in r.tool_calls] == ["search_products", "get_price_and_stock"]
    assert fake.calls[0]["model"] == "claude-opus-5-5" and len(fake.calls) == 3
    msgs = agent.sessions.get("k1").messages
    assert msgs[-2]["content"][0]["tool_use_id"] == "t2" and msgs[-2]["role"] == "user"
    assert "Darija" in SYSTEM_PROMPT


def test_memory_is_per_customer(db):
    fake = FakeClient([NS(stop_reason="end_turn", content=[text("a")]), NS(stop_reason="end_turn", content=[text("b")])])
    agent = ClaudeAgent(db, client=fake)
    agent.respond("u1", "slm")
    agent.respond("u2", "slm")
    assert [c["n"] for c in fake.calls] == [1, 1]


def test_tool_error_flagged_and_guard_blocks_invented_price(db):
    fake = FakeClient([
        NS(stop_reason="tool_use", content=[tool_use("t1", "get_price_and_stock", sku="NOPE")]),
        NS(stop_reason="end_turn", content=[text("Ça coûte 1 000 DA")]),
    ])
    agent = ClaudeAgent(db, client=fake)
    r = agent.respond("k2", "prix ?")
    assert r.escalated and "1 000" not in r.text
    assert r.tool_calls[0].result["ok"] is False
    assert db.one("SELECT COUNT(*) AS n FROM escalations")["n"] == 1


def test_refusal_stop_reason(db):
    fake = FakeClient([NS(stop_reason="refusal", content=[])])
    r = ClaudeAgent(db, client=fake).respond("k3", "bonjour")
    assert r.text
