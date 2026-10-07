"""The player's bankroll."""

from __future__ import annotations

from .money import Cents, fmt


class InsufficientFundsError(Exception):
    def __init__(self, needed: Cents, available: Cents) -> None:
        super().__init__(f"need {fmt(needed)}, have {fmt(available)}")
        self.needed = needed
        self.available = available


class Wallet:
    """Chips the player owns but has not yet put on a table.

    Games debit a wager when it is placed and credit stake plus winnings when it is
    settled, so the balance never includes chips that are currently in play.
    """

    def __init__(self, balance: Cents = 0) -> None:
        if balance < 0:
            raise ValueError("balance cannot be negative")
        self._balance = balance

    @property
    def balance(self) -> Cents:
        return self._balance

    def can_afford(self, amount: Cents) -> bool:
        return 0 <= amount <= self._balance

    def debit(self, amount: Cents) -> None:
        if amount < 0:
            raise ValueError("cannot debit a negative amount")
        if amount > self._balance:
            raise InsufficientFundsError(amount, self._balance)
        self._balance -= amount

    def credit(self, amount: Cents) -> None:
        if amount < 0:
            raise ValueError("cannot credit a negative amount")
        self._balance += amount

    def __repr__(self) -> str:
        return f"Wallet({fmt(self._balance)})"
