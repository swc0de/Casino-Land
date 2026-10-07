"""Chip denominations and how an amount is broken into physical chips."""

from __future__ import annotations

from .money import Cents, dollars

#: Largest first. 50¢ pieces exist so 3:2 blackjack payouts on odd bets can be paid exactly.
DENOMINATIONS: tuple[Cents, ...] = (
    dollars(25_000),
    dollars(5_000),
    dollars(1_000),
    dollars(500),
    dollars(100),
    dollars(25),
    dollars(5),
    dollars(1),
    50,
)

#: Chips offered in the betting rack at the tables.
BETTING_CHIPS: tuple[Cents, ...] = (
    dollars(1),
    dollars(5),
    dollars(25),
    dollars(100),
    dollars(500),
    dollars(1_000),
)


def break_into_chips(
    amount: Cents, denominations: tuple[Cents, ...] = DENOMINATIONS
) -> list[Cents]:
    """Fewest chips that make up ``amount``, largest first.

    Anything below the smallest denomination is left out (it is too small to
    show as a chip); the wallet still holds the exact amount.
    """
    if amount < 0:
        raise ValueError("amount cannot be negative")
    chips: list[Cents] = []
    for denom in sorted(denominations, reverse=True):
        count, amount = divmod(amount, denom)
        chips.extend([denom] * count)
    return chips
