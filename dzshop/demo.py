"""Scripted offline demo: greeting -> price in Darija -> order -> confirmation -> tracking."""

from __future__ import annotations

import sys

from .db import Database
from .offline import OfflineAgent

DEMO_DARIJA = [
    "slm",
    "ch7al soum la montre?",
    "n7eb ncommandi 2",
    "Oran",
    "Karim Benali",
    "0661 23 45 67",
    "Cité 500 logements, Es Senia",
    "iyeh confirmi",
    "win wsslet commande?",
]


def run(messages: list[str], customer: str = "demo", db: Database | None = None) -> list:
    db = db or Database()
    agent = OfflineAgent(db)
    out = []
    for m in messages:
        out.append((m, agent.respond(customer, m)))
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for msg, reply in run(DEMO_DARIJA):
        print(f"Customer: {msg}")
        print(f"Agent   : {reply.text}")
        if reply.tool_calls:
            print("          [tools: " + ", ".join(c.name for c in reply.tool_calls) + "]")
        print()


if __name__ == "__main__":
    main()
