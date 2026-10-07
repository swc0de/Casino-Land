from __future__ import annotations

import pytest

from neon_royale.core.chips import BETTING_CHIPS, DENOMINATIONS, break_into_chips
from neon_royale.core.money import dollars


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, []),
        (dollars(1), [dollars(1)]),
        (dollars(7.5), [dollars(5), dollars(1), dollars(1), 50]),
        (dollars(135), [dollars(100), dollars(25), dollars(5), dollars(5)]),
        (dollars(1_630), [dollars(1_000), dollars(500), dollars(100), dollars(25), dollars(5)]),
    ],
)
def test_break_into_chips(amount: int, expected: list[int]) -> None:
    assert break_into_chips(amount) == expected


def test_breakdown_sums_to_amount_for_whole_half_dollars() -> None:
    for amount in range(0, dollars(3_000), 50 * 37):
        assert sum(break_into_chips(amount)) == amount


def test_odd_cents_are_left_off() -> None:
    assert sum(break_into_chips(dollars(1) + 7)) == dollars(1)


def test_negative_is_rejected() -> None:
    with pytest.raises(ValueError):
        break_into_chips(-1)


def test_betting_chips_are_real_denominations() -> None:
    assert set(BETTING_CHIPS) <= set(DENOMINATIONS)
    assert list(BETTING_CHIPS) == sorted(BETTING_CHIPS)
