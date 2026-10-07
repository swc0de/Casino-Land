"""The poker room: your seat, your buy-in, and the bots who come and go."""

from __future__ import annotations

import random

from ..money import Cents, dollars
from ..wallet import InsufficientFundsError, Wallet
from .ai import ROSTER
from .engine import CHIP, PokerTable, Seat

SEATS = 6
HUMAN_SEAT = 0
SMALL_BLIND = dollars(5)
BIG_BLIND = dollars(10)
MIN_BUY_IN = 40 * BIG_BLIND
MAX_BUY_IN = 200 * BIG_BLIND
DEFAULT_BUY_IN = 100 * BIG_BLIND


class RoomError(Exception):
    pass


class PokerRoom:
    def __init__(self, wallet: Wallet, rng: random.Random | None = None) -> None:
        self.wallet = wallet
        self.rng = rng or random.Random()
        self.table = PokerTable(
            [None] * SEATS, SMALL_BLIND, BIG_BLIND, self.rng, button=self.rng.randrange(SEATS)
        )
        self.bought_in: Cents = 0  # total chips brought to the table this session
        self.fill_seats()

    @property
    def human(self) -> Seat | None:
        return self.table.seats[HUMAN_SEAT]

    @property
    def seated(self) -> bool:
        return self.human is not None

    @property
    def stack(self) -> Cents:
        return self.human.stack if self.human else 0

    def _new_bot(self) -> Seat:
        taken = {s.name for s in self.table.seats if s is not None}
        name, profile, color = self.rng.choice([r for r in ROSTER if r[0] not in taken])
        stack = self.rng.randint(60, 160) * BIG_BLIND
        return Seat(name, stack, profile=profile, color=color)

    def fill_seats(self) -> list[int]:
        """Replace busted bots and fill empty bot seats. Returns the seats that changed."""
        if self.table.in_hand:
            raise RoomError("can't change seats during a hand")
        changed = []
        for i in range(SEATS):
            if i == HUMAN_SEAT:
                continue
            seat = self.table.seats[i]
            if seat is None or seat.stack == 0:
                self.table.seats[i] = self._new_bot()
                changed.append(i)
        return changed

    def buy_in_range(self) -> tuple[Cents, Cents]:
        top = min(MAX_BUY_IN - self.stack, self.wallet.balance)
        top -= top % CHIP
        low = max(CHIP, MIN_BUY_IN - self.stack) if self.stack < MIN_BUY_IN else CHIP
        return low, top

    def sit_down(self, amount: Cents) -> None:
        if self.seated:
            raise RoomError("already seated")
        if not MIN_BUY_IN <= amount <= MAX_BUY_IN or amount % CHIP:
            raise RoomError("buy-in must be between the table minimum and maximum")
        try:
            self.wallet.debit(amount)
        except InsufficientFundsError as exc:
            raise RoomError("not enough chips for that buy-in") from exc
        self.table.seats[HUMAN_SEAT] = Seat("You", amount, is_human=True, color=(255, 230, 120))
        self.bought_in += amount

    def top_up(self, amount: Cents) -> None:
        """Add chips between hands (up to the maximum buy-in)."""
        if not self.seated:
            raise RoomError("not seated")
        if self.table.in_hand:
            raise RoomError("wait for the hand to finish")
        low, high = self.buy_in_range()
        if not low <= amount <= high or amount % CHIP:
            raise RoomError("that top-up is outside the table limits")
        self.wallet.debit(amount)
        self.human.stack += amount
        self.bought_in += amount

    def cash_out(self) -> Cents:
        """Leave the table and put the chips back in the wallet."""
        if self.table.in_hand:
            raise RoomError("finish the hand before leaving")
        if not self.seated:
            return 0
        amount = self.human.stack
        self.wallet.credit(amount)
        self.table.seats[HUMAN_SEAT] = None
        return amount
