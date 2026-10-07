from __future__ import annotations

import pytest

from neon_royale.core.money import dollars, fmt


@pytest.mark.parametrize(
    ("amount", "cents"),
    [(0, 0), (1, 100), (7.5, 750), (22.5, 2250), (0.01, 1), (10_000, 1_000_000)],
)
def test_dollars(amount: float, cents: int) -> None:
    assert dollars(amount) == cents


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "$0"),
        (500, "$5"),
        (2250, "$22.50"),
        (5, "$0.05"),
        (123_456_700, "$1,234,567"),
        (-1500, "-$15"),
    ],
)
def test_fmt(cents: int, text: str) -> None:
    assert fmt(cents) == text


def test_fmt_signed() -> None:
    assert fmt(1000, signed=True) == "+$10"
    assert fmt(-1000, signed=True) == "-$10"
    assert fmt(0, signed=True) == "$0"


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (dollars(500), "$500"),
        (dollars(1_000), "$1K"),
        (dollars(2_500), "$2.5K"),
        (dollars(25_000), "$25K"),
        (dollars(1_500_000), "$1.5M"),
    ],
)
def test_fmt_compact(cents: int, text: str) -> None:
    assert fmt(cents, compact=True) == text
