"""Guard that refuses to let the agent state prices / stock that did not come from the database.

Every tool result is `observe()`d: its money and stock numbers become the only numbers the agent is
allowed to quote in the current turn. `check()` scans a draft reply and reports anything else.
"""

from __future__ import annotations

import re
from typing import Any

MONEY_KEYS = {"price_dzd", "fee_dzd", "subtotal_dzd", "shipping_fee_dzd", "total_dzd", "unit_price_dzd", "line_total_dzd"}
STOCK_KEYS = {"stock"}

_CUR = r"(?:DA|DZD|dzd|da|دج|د\.ج|دينار|دينارا)"
_MONEY_RE = re.compile(rf"(\d[\d  .,]*\d|\d)\s*{_CUR}(?![A-Za-z])")
_STOCK_RE = re.compile(
    r"(\d+)\s*(?:pi[eè]ces?\s+(?:en\s+stock|disponibles?|restantes?)|en\s+stock|in\s+stock|"
    r"(?:قطعة|قطع|حبة)\s+(?:متوفرة|متوفر|متاحة|في\s+المخزون))",
    re.IGNORECASE,
)


def _walk(obj: Any, money: set[int], stock: set[int]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if k in MONEY_KEYS:
                    money.add(int(v))
                elif k in STOCK_KEYS:
                    stock.add(int(v))
            else:
                _walk(v, money, stock)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, money, stock)


class PriceStockGuard:
    def __init__(self) -> None:
        self.money: set[int] = set()
        self.stock: set[int] = set()

    def reset(self) -> None:
        self.money.clear()
        self.stock.clear()

    def observe(self, tool_result: Any) -> None:
        _walk(tool_result, self.money, self.stock)

    def check(self, reply: str) -> list[str]:
        """Return the list of unverified amounts / stock figures found in `reply` (empty = OK)."""
        problems: list[str] = []
        for m in _MONEY_RE.finditer(reply):
            digits = re.sub(r"[  .,]", "", m.group(1))
            if digits and int(digits) not in self.money:
                problems.append(f"price {digits}")
        for m in _STOCK_RE.finditer(reply):
            if int(m.group(1)) not in self.stock:
                problems.append(f"stock {m.group(1)}")
        return problems
