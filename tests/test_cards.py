from __future__ import annotations

import random
from collections import Counter

import pytest

from neon_royale.core.cards import Card, Rank, Shoe, Suit, cards, full_deck


def test_full_deck_is_52_unique_cards() -> None:
    deck = full_deck()
    assert len(deck) == 52
    assert len(set(deck)) == 52


@pytest.mark.parametrize(
    ("text", "rank", "suit"),
    [
        ("As", Rank.ACE, Suit.SPADES),
        ("Td", Rank.TEN, Suit.DIAMONDS),
        ("10h", Rank.TEN, Suit.HEARTS),
        ("2c", Rank.TWO, Suit.CLUBS),
        ("q♥", Rank.QUEEN, Suit.HEARTS),
    ],
)
def test_parse(text: str, rank: Rank, suit: Suit) -> None:
    assert Card.parse(text) == Card(rank, suit)


@pytest.mark.parametrize("bad", ["", "A", "1s", "Ax", "11h"])
def test_parse_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        Card.parse(bad)


def test_round_trip_and_pretty() -> None:
    for card in full_deck():
        assert Card.parse(str(card)) == card
    assert Card.parse("Th").pretty == "10♥"
    assert cards("As Kd") == [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.DIAMONDS)]


def test_suit_colours() -> None:
    assert Suit.HEARTS.is_red and Suit.DIAMONDS.is_red
    assert not Suit.SPADES.is_red and not Suit.CLUBS.is_red


def test_shoe_contains_every_card_once_per_deck() -> None:
    shoe = Shoe(decks=6, rng=random.Random(1))
    drawn = Counter(shoe.draw() for _ in range(shoe.size))
    assert shoe.size == 312
    assert set(drawn.values()) == {6}
    assert len(drawn) == 52


def test_shoe_is_deterministic_with_seed() -> None:
    a = Shoe(decks=2, rng=random.Random(42))
    b = Shoe(decks=2, rng=random.Random(42))
    assert [a.draw() for _ in range(20)] == [b.draw() for _ in range(20)]


def test_cut_card() -> None:
    shoe = Shoe(decks=1, rng=random.Random(3), penetration=0.75)
    assert shoe.cut_position == 39
    for _ in range(38):
        shoe.draw()
    assert not shoe.needs_shuffle
    shoe.draw()
    assert shoe.needs_shuffle
    shoe.shuffle()
    assert shoe.remaining == 52 and not shoe.needs_shuffle


def test_shoe_reshuffles_rather_than_running_dry() -> None:
    shoe = Shoe(decks=1, rng=random.Random(5))
    for _ in range(60):
        shoe.draw()
    assert shoe.dealt == 8


def test_stacked_shoe_deals_in_order_and_never_shuffles() -> None:
    shoe = Shoe.stacked(["As", "Kd", "7h"])
    shoe.shuffle()
    assert not shoe.needs_shuffle
    assert [str(shoe.draw()) for _ in range(3)] == ["As", "Kd", "7h"]
    with pytest.raises(RuntimeError):
        shoe.draw()


def test_shoe_validates_arguments() -> None:
    with pytest.raises(ValueError):
        Shoe(decks=0)
    with pytest.raises(ValueError):
        Shoe(penetration=0)
