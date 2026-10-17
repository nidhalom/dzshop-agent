"""Per-customer conversation memory shared by the Claude agent and the offline agent."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    input: dict
    result: dict


@dataclass
class AgentReply:
    text: str
    lang: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    escalated: bool = False
    mode: str = "offline"


@dataclass
class Draft:
    """Order being collected in the offline slot-filling flow."""
    sku: str | None = None
    qty: int = 1
    wilaya: str | None = None
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    awaiting: str | None = None
    active: bool = False


@dataclass
class Session:
    customer_id: str
    lang: str = "fr"
    messages: list[Any] = field(default_factory=list)  # Claude message history
    transcript: list[tuple[str, str]] = field(default_factory=list)  # (role, text)
    draft: Draft = field(default_factory=Draft)
    last_sku: str | None = None
    phone: str | None = None  # phone given by this customer (used to authorise order lookups)
    pending_order: str | None = None  # order awaiting customer confirmation
    last_order: str | None = None
    unknown_streak: int = 0


class SessionStore:
    def __init__(self) -> None:
        self._s: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, customer_id: str) -> Session:
        with self._lock:
            return self._s.setdefault(customer_id, Session(customer_id))

    def clear(self, customer_id: str) -> None:
        with self._lock:
            self._s.pop(customer_id, None)
