"""European (single-zero) roulette: wheel, bets, payouts and a betting round.

The betting layout has three rows of twelve numbers. Number ``n`` sits in street
``(n - 1) // 3`` (a column of the printed layout, read left to right) and row
``(n - 1) % 3``, where row 0 holds 1, 4, 7 … and row 2 holds 3, 6, 9 ….

House edge is 1/37 (2.70%) on every bet: each bet's payout ``p`` satisfies
``p + 1 == 36 / len(numbers)``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from .money import Cents, dollars, fmt
from .wallet import InsufficientFundsError, Wallet

WHEEL_ORDER: tuple[int, ...] = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)  # fmt: skip
POCKETS = len(WHEEL_ORDER)

RED_NUMBERS = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})

MIN_BET: Cents = dollars(1)
MAX_TABLE: Cents = dollars(5_000)  # total on the layout per spin
HISTORY_LENGTH = 20


def color_of(number: int) -> str:
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def street_of(number: int) -> int:
    return (number - 1) // 3


def row_of(number: int) -> int:
    return (number - 1) % 3


class BetKind(Enum):
    STRAIGHT = ("Straight", 35)
    SPLIT = ("Split", 17)
    STREET = ("Street", 11)
    TRIO = ("Trio", 11)
    CORNER = ("Corner", 8)
    FIRST_FOUR = ("First four", 8)
    SIX_LINE = ("Six line", 5)
    DOZEN = ("Dozen", 2)
    COLUMN = ("Column", 2)
    RED = ("Red", 1)
    BLACK = ("Black", 1)
    ODD = ("Odd", 1)
    EVEN = ("Even", 1)
    LOW = ("1 to 18", 1)
    HIGH = ("19 to 36", 1)

    def __init__(self, title: str, payout: int) -> None:
        self.title = title
        self.payout = payout

    @property
    def inside(self) -> bool:
        return self.payout >= 5


@dataclass(frozen=True)
class Bet:
    """A bet type on a set of numbers. Construct with the helper functions below."""

    kind: BetKind
    numbers: frozenset[int]

    @property
    def payout(self) -> int:
        return self.kind.payout

    def wins(self, number: int) -> bool:
        return number in self.numbers

    @property
    def label(self) -> str:
        k = self.kind
        nums = sorted(self.numbers)
        if k is BetKind.STRAIGHT:
            return f"Straight {nums[0]}"
        if k in (BetKind.SPLIT, BetKind.CORNER, BetKind.TRIO):
            return f"{k.title} {'-'.join(map(str, nums))}"
        if k is BetKind.STREET:
            return f"Street {nums[0]}-{nums[-1]}"
        if k is BetKind.SIX_LINE:
            return f"Six line {nums[0]}-{nums[-1]}"
        if k is BetKind.DOZEN:
            return f"Dozen {nums[0]}-{nums[-1]}"
        if k is BetKind.COLUMN:
            return f"Column {row_of(nums[0]) + 1}"
        return k.title


def _bet(kind: BetKind, numbers: set[int] | frozenset[int] | range | list[int]) -> Bet:
    return Bet(kind, frozenset(numbers))


def _check(number: int, allow_zero: bool = False) -> None:
    low = 0 if allow_zero else 1
    if not low <= number <= 36:
        raise ValueError(f"{number} is not on the layout")


def straight(n: int) -> Bet:
    _check(n, allow_zero=True)
    return _bet(BetKind.STRAIGHT, {n})


def split(a: int, b: int) -> Bet:
    _check(a, True)
    _check(b, True)
    a, b = sorted((a, b))
    if a == 0:
        ok = b in (1, 2, 3)
    else:
        same_street = street_of(a) == street_of(b) and b - a == 1
        ok = same_street or b - a == 3
    if not ok:
        raise ValueError(f"{a} and {b} are not next to each other")
    return _bet(BetKind.SPLIT, {a, b})


def street(index: int) -> Bet:
    """Street ``index`` 0..11 covers 3i+1 .. 3i+3."""
    if not 0 <= index <= 11:
        raise ValueError("street index must be 0..11")
    return _bet(BetKind.STREET, range(3 * index + 1, 3 * index + 4))


def trio(high: int) -> Bet:
    """The zero trios: ``trio(1)`` is 0-1-2 and ``trio(3)`` is 0-2-3."""
    if high == 1:
        return _bet(BetKind.TRIO, {0, 1, 2})
    if high == 3:
        return _bet(BetKind.TRIO, {0, 2, 3})
    raise ValueError("trio is 0-1-2 or 0-2-3")


def corner(low: int) -> Bet:
    """The four numbers meeting at ``low``'s far corner: low, low+1, low+3, low+4."""
    _check(low)
    if row_of(low) == 2 or low > 32:
        raise ValueError(f"no corner starting at {low}")
    return _bet(BetKind.CORNER, {low, low + 1, low + 3, low + 4})


def first_four() -> Bet:
    return _bet(BetKind.FIRST_FOUR, {0, 1, 2, 3})


def six_line(index: int) -> Bet:
    """Streets ``index`` and ``index + 1`` (0..10)."""
    if not 0 <= index <= 10:
        raise ValueError("six line index must be 0..10")
    return _bet(BetKind.SIX_LINE, range(3 * index + 1, 3 * index + 7))


def dozen(index: int) -> Bet:
    if not 0 <= index <= 2:
        raise ValueError("dozen index must be 0..2")
    return _bet(BetKind.DOZEN, range(12 * index + 1, 12 * index + 13))


def column(row: int) -> Bet:
    """Column bet on layout row ``row`` (0: 1,4,7…; 2: 3,6,9…)."""
    if not 0 <= row <= 2:
        raise ValueError("column must be 0..2")
    return _bet(BetKind.COLUMN, range(row + 1, 37, 3))


def red() -> Bet:
    return _bet(BetKind.RED, RED_NUMBERS)


def black() -> Bet:
    return _bet(BetKind.BLACK, set(range(1, 37)) - RED_NUMBERS)


def odd() -> Bet:
    return _bet(BetKind.ODD, range(1, 37, 2))


def even() -> Bet:
    return _bet(BetKind.EVEN, range(2, 37, 2))


def low() -> Bet:
    return _bet(BetKind.LOW, range(1, 19))


def high() -> Bet:
    return _bet(BetKind.HIGH, range(19, 37))


def all_bets() -> list[Bet]:
    """Every distinct bet the layout offers."""
    bets: list[Bet] = [straight(n) for n in range(37)]
    bets += [split(0, n) for n in (1, 2, 3)]
    for n in range(1, 37):
        if row_of(n) < 2:
            bets.append(split(n, n + 1))
        if n <= 33:
            bets.append(split(n, n + 3))
        if row_of(n) < 2 and n <= 32:
            bets.append(corner(n))
    bets += [street(i) for i in range(12)]
    bets += [trio(1), trio(3), first_four()]
    bets += [six_line(i) for i in range(11)]
    bets += [dozen(i) for i in range(3)] + [column(r) for r in range(3)]
    bets += [red(), black(), odd(), even(), low(), high()]
    return bets


# -- a round at the table -------------------------------------------------------------


class TableError(Exception):
    """A bet the table won't accept (limits, wrong phase)."""


@dataclass(frozen=True)
class Payout:
    bet: Bet
    stake: Cents
    won: bool

    @property
    def returned(self) -> Cents:
        """Stake plus winnings for a winning bet, nothing for a loser."""
        return self.stake * (self.bet.payout + 1) if self.won else 0


@dataclass(frozen=True)
class SpinResult:
    number: int
    payouts: tuple[Payout, ...]

    @property
    def color(self) -> str:
        return color_of(self.number)

    @property
    def wagered(self) -> Cents:
        return sum(p.stake for p in self.payouts)

    @property
    def returned(self) -> Cents:
        return sum(p.returned for p in self.payouts)

    @property
    def net(self) -> Cents:
        return self.returned - self.wagered


@dataclass
class RouletteTable:
    """Betting, spinning and settling, with the wallet debited as chips go down.

    ``spin`` decides the number and computes every payout but pays nothing; the
    screen animates the wheel and then calls ``settle``. Bets left unspun can be
    taken back with ``clear`` (or ``undo``) and are refunded in full.
    """

    wallet: Wallet
    rng: random.Random = field(default_factory=random.Random)
    min_bet: Cents = MIN_BET
    max_table: Cents = MAX_TABLE
    bets: dict[Bet, Cents] = field(default_factory=dict)
    history: list[int] = field(default_factory=list)
    last_bets: dict[Bet, Cents] = field(default_factory=dict)
    pending: SpinResult | None = None
    _placements: list[tuple[Bet, Cents]] = field(default_factory=list)

    @property
    def total_bet(self) -> Cents:
        return sum(self.bets.values())

    @property
    def spinning(self) -> bool:
        return self.pending is not None

    def _require_betting(self) -> None:
        if self.pending is not None:
            raise TableError("no more bets: the ball is spinning")

    def place(self, bet: Bet, amount: Cents) -> None:
        self._require_betting()
        if amount <= 0:
            raise TableError("bet must be positive")
        if self.bets.get(bet, 0) + amount < self.min_bet:
            raise TableError(f"minimum bet is {fmt(self.min_bet)}")
        if self.total_bet + amount > self.max_table:
            raise TableError("that would go over the table limit")
        try:
            self.wallet.debit(amount)
        except InsufficientFundsError as exc:
            raise TableError("not enough chips") from exc
        self.bets[bet] = self.bets.get(bet, 0) + amount
        self._placements.append((bet, amount))

    def remove(self, bet: Bet) -> Cents:
        """Take a whole bet back off the layout. Returns the refund."""
        self._require_betting()
        amount = self.bets.pop(bet, 0)
        self.wallet.credit(amount)
        self._placements = [(b, a) for b, a in self._placements if b != bet]
        return amount

    def undo(self) -> Bet | None:
        """Take back the most recent chip placed. Returns the bet it came off."""
        self._require_betting()
        if not self._placements:
            return None
        bet, amount = self._placements.pop()
        self.bets[bet] -= amount
        if self.bets[bet] <= 0:
            del self.bets[bet]
        self.wallet.credit(amount)
        return bet

    def clear(self) -> Cents:
        self._require_betting()
        refund = self.total_bet
        self.wallet.credit(refund)
        self.bets.clear()
        self._placements.clear()
        return refund

    def can_rebet(self) -> bool:
        cost = sum(self.last_bets.values())
        return (
            not self.spinning
            and bool(self.last_bets)
            and self.wallet.can_afford(cost)
            and self.total_bet + cost <= self.max_table
        )

    def rebet(self) -> bool:
        """Repeat last spin's bets on top of anything already placed."""
        if not self.can_rebet():
            return False
        for bet, amount in self.last_bets.items():
            self.place(bet, amount)
        return True

    def can_double(self) -> bool:
        total = self.total_bet
        return (
            not self.spinning
            and total > 0
            and self.wallet.can_afford(total)
            and total * 2 <= self.max_table
        )

    def double(self) -> bool:
        if not self.can_double():
            return False
        for bet, amount in list(self.bets.items()):
            self.place(bet, amount)
        return True

    def spin(self, number: int | None = None) -> SpinResult:
        """Close betting and decide the result. ``number`` forces it (tests, demos)."""
        self._require_betting()
        if not self.bets:
            raise TableError("place a bet first")
        if number is None:
            number = self.rng.choice(WHEEL_ORDER)
        elif number not in WHEEL_ORDER:
            raise ValueError(f"{number} is not on the wheel")
        payouts = tuple(Payout(bet, stake, bet.wins(number)) for bet, stake in self.bets.items())
        self.pending = SpinResult(number, payouts)
        return self.pending

    def settle(self) -> SpinResult:
        """Pay the winners and clear the layout, ready for the next spin."""
        result = self.pending
        if result is None:
            raise TableError("nothing to settle")
        self.wallet.credit(result.returned)
        self.history.insert(0, result.number)
        del self.history[HISTORY_LENGTH:]
        self.last_bets = dict(self.bets)
        self.bets.clear()
        self._placements.clear()
        self.pending = None
        return result

    def abandon(self) -> Cents:
        """Leave the table cleanly (e.g. the window closes).

        A spin already under way is settled (its number was decided when the ball
        was launched); bets not yet spun are refunded. Returns what went back to the
        wallet.
        """
        if self.pending is not None:
            return self.settle().returned
        return self.clear()
