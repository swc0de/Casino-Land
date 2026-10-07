"""Playing cards and shoes shared by Blackjack and Poker."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    @property
    def symbol(self) -> str:
        return "♣♦♥♠"[self]

    @property
    def letter(self) -> str:
        return "cdhs"[self]

    @property
    def is_red(self) -> bool:
        return self in (Suit.DIAMONDS, Suit.HEARTS)


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def label(self) -> str:
        """Corner index as printed on a card: ``2``…``10``, ``J``, ``Q``, ``K``, ``A``."""
        return _RANK_LABELS[self]

    @property
    def letter(self) -> str:
        """Single-character code used in hand notation (``T`` for ten)."""
        return "T" if self is Rank.TEN else self.label

    @property
    def is_face(self) -> bool:
        return self in (Rank.JACK, Rank.QUEEN, Rank.KING)


_RANK_LABELS = {r: str(int(r)) for r in Rank if r <= 10} | {
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
}
_RANK_BY_LETTER = {r.letter: r for r in Rank} | {"10": Rank.TEN}
_SUIT_BY_LETTER = {s.letter: s for s in Suit} | {s.symbol: s for s in Suit}


@dataclass(frozen=True, slots=True, order=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.letter}{self.suit.letter}"

    def __repr__(self) -> str:
        return f"Card({self})"

    @property
    def pretty(self) -> str:
        return f"{self.rank.label}{self.suit.symbol}"

    @classmethod
    def parse(cls, text: str) -> Card:
        """Parse ``"Ah"``, ``"Td"``, ``"10s"`` or ``"Q♥"``."""
        text = text.strip()
        if len(text) < 2:
            raise ValueError(f"not a card: {text!r}")
        rank_text, suit_text = text[:-1], text[-1]
        try:
            return cls(_RANK_BY_LETTER[rank_text.upper()], _SUIT_BY_LETTER[suit_text.lower()])
        except KeyError:
            raise ValueError(f"not a card: {text!r}") from None


def cards(text: str) -> list[Card]:
    """Parse a space-separated list of cards, e.g. ``cards("As Kd 7h")``."""
    return [Card.parse(token) for token in text.split()]


def full_deck() -> list[Card]:
    return [Card(rank, suit) for suit in Suit for rank in Rank]


class Shoe:
    """One or more decks dealt from the top, with a cut card.

    ``needs_shuffle`` turns true once the cut card has come out; games check it
    between rounds, as a dealer would, rather than mid-hand.
    """

    def __init__(
        self,
        decks: int = 1,
        rng: random.Random | None = None,
        penetration: float = 1.0,
    ) -> None:
        if decks < 1:
            raise ValueError("a shoe needs at least one deck")
        if not 0.0 < penetration <= 1.0:
            raise ValueError("penetration must be in (0, 1]")
        self.decks = decks
        self.penetration = penetration
        self._rng = rng or random.Random()
        self._cards: list[Card] = []
        self._next = 0
        self._stacked = False
        self.shuffle()

    @classmethod
    def stacked(cls, order: Iterable[Card | str]) -> Shoe:
        """A shoe that deals exactly ``order`` and never reshuffles. For tests and demos."""
        shoe = cls.__new__(cls)
        shoe.decks = 1
        shoe.penetration = 1.0
        shoe._rng = random.Random(0)
        shoe._cards = [c if isinstance(c, Card) else Card.parse(c) for c in order]
        shoe._next = 0
        shoe._stacked = True
        return shoe

    @property
    def size(self) -> int:
        return len(self._cards)

    @property
    def remaining(self) -> int:
        return len(self._cards) - self._next

    @property
    def dealt(self) -> int:
        return self._next

    @property
    def cut_position(self) -> int:
        return int(len(self._cards) * self.penetration)

    @property
    def needs_shuffle(self) -> bool:
        if self._stacked:
            return False
        return self._next >= self.cut_position

    def shuffle(self) -> None:
        if self._stacked:
            return
        self._cards = full_deck() * self.decks
        self._rng.shuffle(self._cards)
        self._next = 0

    def draw(self) -> Card:
        if self._next >= len(self._cards):
            if self._stacked:
                raise RuntimeError("stacked shoe ran out of cards")
            # Past the cut card and out of cards mid-round: a real dealer would
            # shuffle the discards back in. Reshuffling the full shoe is equivalent
            # for play purposes and keeps the round going.
            self.shuffle()
        card = self._cards[self._next]
        self._next += 1
        return card
