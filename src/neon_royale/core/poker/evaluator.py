"""Poker hand evaluation for 5 to 7 cards.

``evaluate`` returns an integer score: a higher score is a better hand and equal
scores tie. The score packs the category in the top bits and up to five tie-break
ranks below it, so comparing hands is a single integer comparison. It works on
rank counts and per-suit rank bitmasks rather than trying all 21 five-card subsets,
which keeps it fast enough for Monte Carlo equity estimates in pure Python.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import IntEnum
from itertools import combinations

from ..cards import Card


class Category(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8

    @property
    def title(self) -> str:
        return _TITLES[self]


_TITLES = {
    Category.HIGH_CARD: "High card",
    Category.PAIR: "Pair",
    Category.TWO_PAIR: "Two pair",
    Category.THREE_OF_A_KIND: "Three of a kind",
    Category.STRAIGHT: "Straight",
    Category.FLUSH: "Flush",
    Category.FULL_HOUSE: "Full house",
    Category.FOUR_OF_A_KIND: "Four of a kind",
    Category.STRAIGHT_FLUSH: "Straight flush",
}

_SHIFT = 20  # five tie-break ranks of 4 bits each sit below the category


def _score(category: Category, ranks: Sequence[int]) -> int:
    value = int(category) << _SHIFT
    for i, rank in enumerate(ranks[:5]):
        value |= rank << (16 - 4 * i)
    return value


def category_of(score: int) -> Category:
    return Category(score >> _SHIFT)


def tiebreak_ranks(score: int) -> list[int]:
    return [(score >> (16 - 4 * i)) & 0xF for i in range(5)]


def _straight_high(mask: int) -> int:
    """Highest card of a straight in ``mask`` (bit r set for rank r), or 0."""
    if mask & (1 << 14):
        mask |= 1 << 1  # the ace also plays low: A-2-3-4-5
    for high in range(14, 4, -1):
        window = 0b11111 << (high - 4)
        if mask & window == window:
            return high
    return 0


def _top_bits(mask: int, count: int) -> list[int]:
    ranks = []
    for rank in range(14, 1, -1):
        if mask & (1 << rank):
            ranks.append(rank)
            if len(ranks) == count:
                break
    return ranks


def evaluate(cards: Iterable[Card]) -> int:
    """Score the best five-card hand among ``cards`` (5 to 7 cards)."""
    counts = [0] * 15
    suit_masks = [0, 0, 0, 0]
    rank_mask = 0
    n = 0
    for card in cards:
        r = int(card.rank)
        counts[r] += 1
        suit_masks[card.suit] |= 1 << r
        rank_mask |= 1 << r
        n += 1
    if not 5 <= n <= 7:
        raise ValueError("evaluate needs 5 to 7 cards")

    for mask in suit_masks:
        if mask.bit_count() >= 5:
            high = _straight_high(mask)
            if high:
                return _score(Category.STRAIGHT_FLUSH, [high])
            flush = _score(Category.FLUSH, _top_bits(mask, 5))
            break
    else:
        flush = 0

    quads: list[int] = []
    trips: list[int] = []
    pairs: list[int] = []
    singles: list[int] = []
    for rank in range(14, 1, -1):
        c = counts[rank]
        if c == 4:
            quads.append(rank)
        elif c == 3:
            trips.append(rank)
        elif c == 2:
            pairs.append(rank)
        elif c == 1:
            singles.append(rank)

    if quads:
        kicker = max([r for r in range(2, 15) if counts[r] and r != quads[0]], default=0)
        return _score(Category.FOUR_OF_A_KIND, [quads[0], kicker])
    if trips and (len(trips) > 1 or pairs):
        pair = max(trips[1:] + pairs)
        return _score(Category.FULL_HOUSE, [trips[0], pair])
    if flush:
        return flush
    high = _straight_high(rank_mask)
    if high:
        return _score(Category.STRAIGHT, [high])
    if trips:
        return _score(Category.THREE_OF_A_KIND, [trips[0], *singles[:2]])
    if len(pairs) >= 2:
        kicker = max(pairs[2:] + singles[:1], default=0)
        return _score(Category.TWO_PAIR, [pairs[0], pairs[1], kicker])
    if pairs:
        return _score(Category.PAIR, [pairs[0], *singles[:3]])
    return _score(Category.HIGH_CARD, singles[:5])


_RANK_NAMES = {
    2: ("Two", "Twos"),
    3: ("Three", "Threes"),
    4: ("Four", "Fours"),
    5: ("Five", "Fives"),
    6: ("Six", "Sixes"),
    7: ("Seven", "Sevens"),
    8: ("Eight", "Eights"),
    9: ("Nine", "Nines"),
    10: ("Ten", "Tens"),
    11: ("Jack", "Jacks"),
    12: ("Queen", "Queens"),
    13: ("King", "Kings"),
    14: ("Ace", "Aces"),
}


def _one(rank: int) -> str:
    return _RANK_NAMES[rank][0]


def _many(rank: int) -> str:
    return _RANK_NAMES[rank][1]


def describe(score: int) -> str:
    """Human-readable name, e.g. "Full house, Kings over Sevens"."""
    category = category_of(score)
    r = tiebreak_ranks(score)
    if category is Category.STRAIGHT_FLUSH:
        return "Royal flush" if r[0] == 14 else f"Straight flush, {_one(r[0])} high"
    if category is Category.FOUR_OF_A_KIND:
        return f"Four {_many(r[0])}"
    if category is Category.FULL_HOUSE:
        return f"Full house, {_many(r[0])} over {_many(r[1])}"
    if category is Category.FLUSH:
        return f"Flush, {_one(r[0])} high"
    if category is Category.STRAIGHT:
        return f"Straight, {_one(r[0])} high"
    if category is Category.THREE_OF_A_KIND:
        return f"Three {_many(r[0])}"
    if category is Category.TWO_PAIR:
        return f"Two pair, {_many(r[0])} and {_many(r[1])}"
    if category is Category.PAIR:
        return f"Pair of {_many(r[0])}"
    return f"{_one(r[0])} high"


def best_five(cards: Sequence[Card]) -> list[Card]:
    """The five cards that make the best hand (used to highlight a winning hand)."""
    if len(cards) <= 5:
        return list(cards)
    target = evaluate(cards)
    for combo in combinations(cards, 5):
        if evaluate(combo) == target:
            return sorted(combo, key=lambda c: (-int(c.rank), c.suit))
    raise AssertionError("no five-card subset matches the best score")  # pragma: no cover


__all__ = [
    "Category",
    "best_five",
    "category_of",
    "describe",
    "evaluate",
    "tiebreak_ranks",
]
