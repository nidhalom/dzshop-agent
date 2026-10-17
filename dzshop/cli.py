"""Interactive CLI chat: `python -m dzshop.cli`."""

from __future__ import annotations

import os
import sys

from .claude_agent import build_agent
from .db import Database


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    agent = build_agent(Database(os.environ.get("DZSHOP_DB", ":memory:")))
    print(f"dzshop-agent CLI ({agent.mode} mode). Type 'quit' to exit.")
    while True:
        try:
            msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit"}:
            break
        if msg:
            r = agent.respond("cli", msg)
            print(f"bot> {r.text}")
            if r.tool_calls:
                print("     [tools: " + ", ".join(c.name for c in r.tool_calls) + "]")


if __name__ == "__main__":
    main()
