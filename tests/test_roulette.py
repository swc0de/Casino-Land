from __future__ import annotations

import random
from fractions import Fraction
from itertools import pairwise

import pytest

from neon_royale.core import roulette as r
from neon_royale.core.money import dollars
from neon_royale.core.roulette import BetKind, RouletteTable, TableError
from neon_royale.core.wallet import Wallet


def test_wheel_has_each_number_once() -> None:
    assert sorted(r.WHEEL_ORDER) == list(range(37))
    assert r.WHEEL_ORDER[0] == 0
    assert r.WHEEL_ORDER[1] == 32 and r.WHEEL_ORDER[-1] == 26


def test_wheel_alternates_red_and_black() -> None:
    colours = [r.color_of(n) for n in r.WHEEL_ORDER[1:]]
    assert all(a != b for a, b in pairwise(colours))
    assert colours.count("red") == colours.count("black") == 18


def test_colours() -> None:
    assert r.color_of(0) == "green"
    assert r.color_of(1) == "red" and r.color_of(2) == "black"
    assert r.color_of(10) == "black" and r.color_of(11) == "black"
    assert r.color_of(19) == "red" and r.color_of(36) == "red"


def test_every_bet_has_a_271_percent_house_edge() -> None:
    """Exact expected value over all 37 outcomes is -1/37 of the stake for every bet."""
    for bet in r.all_bets():
        ev = Fraction(0)
        for number in range(37):
            ev += bet.payout if bet.wins(number) else -1
        assert ev / 37 == Fraction(-1, 37), bet.label


def test_payout_matches_coverage() -> None:
    for bet in r.all_bets():
        assert (bet.payout + 1) * len(bet.numbers) == 36, bet.label


def test_all_bets_are_distinct_and_counted() -> None:
    bets = r.all_bets()
    assert len(bets) == len(set(bets))
    counts = {kind: sum(b.kind is kind for b in bets) for kind in BetKind}
    assert counts[BetKind.STRAIGHT] == 37
    assert counts[BetKind.SPLIT] == 3 + 24 + 33  # zero splits, across, down
    assert counts[BetKind.CORNER] == 22
    assert counts[BetKind.STREET] == 12
    assert counts[BetKind.SIX_LINE] == 11
    assert counts[BetKind.TRIO] == 2
    assert counts[BetKind.FIRST_FOUR] == 1


@pytest.mark.parametrize(
    ("bet", "numbers"),
    [
        (r.split(17, 20), {17, 20}),
        (r.split(2, 3), {2, 3}),
        (r.split(0, 2), {0, 2}),
        (r.street(0), {1, 2, 3}),
        (r.street(11), {34, 35, 36}),
        (r.corner(1), {1, 2, 4, 5}),
        (r.corner(32), {32, 33, 35, 36}),
        (r.six_line(10), set(range(31, 37))),
        (r.trio(1), {0, 1, 2}),
        (r.trio(3), {0, 2, 3}),
        (r.dozen(1), set(range(13, 25))),
        (r.column(0), set(range(1, 37, 3))),
        (r.column(2), {3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36}),
        (r.low(), set(range(1, 19))),
        (r.even(), set(range(2, 37, 2))),
    ],
)
def test_bet_coverage(bet: r.Bet, numbers: set[int]) -> None:
    assert bet.numbers == numbers


@pytest.mark.parametrize(
    "make",
    [
        lambda: r.split(3, 4),  # different streets, not vertically adjacent
        lambda: r.split(1, 5),
        lambda: r.split(0, 4),
        lambda: r.corner(3),  # top row has no corner above it
        lambda: r.corner(34),
        lambda: r.street(12),
        lambda: r.six_line(11),
        lambda: r.straight(37),
        lambda: r.trio(2),
        lambda: r.dozen(3),
        lambda: r.column(-1),
    ],
)
def test_invalid_bets_rejected(make) -> None:
    with pytest.raises(ValueError):
        make()


def test_zero_loses_all_outside_bets() -> None:
    for bet in (r.red(), r.black(), r.odd(), r.even(), r.low(), r.high(), r.dozen(0), r.column(0)):
        assert not bet.wins(0)


def test_labels() -> None:
    assert r.straight(17).label == "Straight 17"
    assert r.split(20, 17).label == "Split 17-20"
    assert r.street(2).label == "Street 7-9"
    assert r.column(1).label == "Column 2"
    assert r.red().label == "Red"


# -- table ----------------------------------------------------------------------------


def make_table(balance: float = 1_000) -> RouletteTable:
    return RouletteTable(Wallet(dollars(balance)), random.Random(5))


def test_placing_debits_and_winning_pays_stake_plus_winnings() -> None:
    table = make_table()
    table.place(r.straight(17), dollars(10))
    table.place(r.red(), dollars(20))
    table.place(r.dozen(0), dollars(5))
    assert table.wallet.balance == dollars(965)

    result = table.spin(17)
    assert table.wallet.balance == dollars(965), "nothing paid until settle"
    assert result.wagered == dollars(35)
    # straight 35:1 -> 360, black 17 loses the red bet, dozen 13-24 loses
    assert result.returned == dollars(360)
    table.settle()
    assert table.wallet.balance == dollars(1_325)
    assert table.history == [17]
    assert table.bets == {}


def test_zero_result() -> None:
    table = make_table()
    table.place(r.straight(0), dollars(1))
    table.place(r.even(), dollars(10))
    result = table.spin(0)
    assert result.color == "green"
    assert result.returned == dollars(36)
    assert result.net == dollars(25)


def test_limits_and_funds() -> None:
    table = make_table(100)
    with pytest.raises(TableError, match="minimum"):
        table.place(r.red(), 50)
    with pytest.raises(TableError, match="not enough"):
        table.place(r.red(), dollars(101))
    rich = make_table(10_000)
    rich.place(r.red(), dollars(4_990))
    with pytest.raises(TableError, match="limit"):
        rich.place(r.black(), dollars(11))
    assert rich.wallet.balance == dollars(5_010)


def test_chips_accumulate_on_one_bet() -> None:
    table = make_table()
    table.place(r.red(), 50 * 2)
    table.place(r.red(), dollars(5))
    assert table.bets[r.red()] == dollars(6)


def test_undo_clear_and_remove_refund() -> None:
    table = make_table()
    table.place(r.red(), dollars(5))
    table.place(r.red(), dollars(25))
    table.place(r.straight(7), dollars(1))
    assert table.undo() == r.straight(7)
    assert table.bets == {r.red(): dollars(30)}
    assert table.undo() == r.red()
    assert table.bets == {r.red(): dollars(5)}
    table.place(r.odd(), dollars(10))
    assert table.remove(r.odd()) == dollars(10)
    assert table.clear() == dollars(5)
    assert table.undo() is None
    assert table.wallet.balance == dollars(1_000)


def test_no_betting_while_spinning() -> None:
    table = make_table()
    table.place(r.red(), dollars(5))
    table.spin()
    for action in (
        lambda: table.place(r.black(), dollars(5)),
        table.undo,
        table.clear,
        lambda: table.remove(r.red()),
        table.spin,
    ):
        with pytest.raises(TableError):
            action()
    table.settle()
    with pytest.raises(TableError):
        table.settle()


def test_cannot_spin_without_bets() -> None:
    with pytest.raises(TableError):
        make_table().spin()


def test_rebet_and_double() -> None:
    table = make_table()
    assert not table.can_rebet()
    table.place(r.red(), dollars(10))
    table.place(r.straight(3), dollars(2))
    assert table.double()
    assert table.bets == {r.red(): dollars(20), r.straight(3): dollars(4)}
    table.spin(4)  # black, even: everything loses
    table.settle()
    assert table.wallet.balance == dollars(976)
    assert table.rebet()
    assert table.bets == {r.red(): dollars(20), r.straight(3): dollars(4)}
    assert table.wallet.balance == dollars(952)


def test_rebet_refused_when_unaffordable() -> None:
    table = make_table(30)
    table.place(r.red(), dollars(30))
    table.spin(2)
    table.settle()
    assert table.wallet.balance == 0
    assert not table.rebet()
    assert not table.can_double()


def test_spin_is_random_and_covers_wheel() -> None:
    table = make_table(100_000)
    seen = set()
    for _ in range(2000):
        table.place(r.red(), dollars(1))
        seen.add(table.spin().number)
        table.settle()
    assert seen == set(range(37))
    assert len(table.history) == r.HISTORY_LENGTH


def test_forced_number_must_exist() -> None:
    table = make_table()
    table.place(r.red(), dollars(1))
    with pytest.raises(ValueError):
        table.spin(37)
