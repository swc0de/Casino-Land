"""Money is stored as integer cents everywhere.

Casinos pay fractional amounts (3:2 on a $15 blackjack is $22.50), so whole-dollar
integers are not enough and floats drift. Keeping cents as plain ``int`` makes every
payout exact and trivially comparable in tests.
"""

from __future__ import annotations

Cents = int

CENTS_PER_DOLLAR = 100


def dollars(amount: int | float) -> Cents:
    """Convert a dollar figure to cents, e.g. ``dollars(7.5) == 750``."""
    return round(amount * CENTS_PER_DOLLAR)


def fmt(cents: Cents, *, signed: bool = False, compact: bool = False) -> str:
    """Format cents for display.

    Whole-dollar amounts drop the cents (``$1,250``); others keep them (``$22.50``).
    ``compact`` abbreviates large values for chip labels (``$1K``, ``$2.5M``).
    """
    sign = ""
    if cents < 0:
        sign = "-"
    elif signed and cents > 0:
        sign = "+"
    value = abs(cents)
    if compact and value >= 1_000 * CENTS_PER_DOLLAR:
        for divisor, suffix in (
            (1_000_000_000 * CENTS_PER_DOLLAR, "B"),
            (1_000_000 * CENTS_PER_DOLLAR, "M"),
            (1_000 * CENTS_PER_DOLLAR, "K"),
        ):
            if value >= divisor:
                scaled = value / divisor
                text = f"{scaled:.1f}".rstrip("0").rstrip(".")
                return f"{sign}${text}{suffix}"
    whole, frac = divmod(value, CENTS_PER_DOLLAR)
    if frac:
        return f"{sign}${whole:,}.{frac:02d}"
    return f"{sign}${whole:,}"
