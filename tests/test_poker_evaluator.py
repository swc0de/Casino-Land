from __future__ import annotations

import random
from collections import Counter
from itertools import combinations

import pytest

from neon_royale.core.cards import cards, full_deck
from neon_royale.core.poker.evaluator import (
    Category,
    best_five,
    category_of,
    describe,
    evaluate,
)


@pytest.mark.parametrize(
    ("hand", "category"),
    [
        ("As Ks Qs Js Ts", Category.STRAIGHT_FLUSH),
        ("5d 4d 3d 2d Ad", Category.STRAIGHT_FLUSH),
        ("9c 9d 9h 9s 2c", Category.FOUR_OF_A_KIND),
        ("Kc Kd Kh 7s 7c", Category.FULL_HOUSE),
        ("Ah 9h 7h 4h 2h", Category.FLUSH),
        ("Ac 2d 3h 4s 5c", Category.STRAIGHT),
        ("Tc Jd Qh Ks Ac", Category.STRAIGHT),
        ("7c 7d 7h Ks 2c", Category.THREE_OF_A_KIND),
        ("7c 7d Kh Ks 2c", Category.TWO_PAIR),
        ("7c 7d Kh Qs 2c", Category.PAIR),
        ("Ac Jd 8h 6s 2c", Category.HIGH_CARD),
        ("Qc Kd Ah 2s 3c", Category.HIGH_CARD),  # no wrap-around straight
    ],
)
def test_categories(hand: str, category: Category) -> None:
    assert category_of(evaluate(cards(hand))) is category


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        ("As Ks Qs Js Ts", "9s 8s 7s 6s 5s"),
        ("6d 5d 4d 3d 2d", "5c 4c 3c 2c Ac"),  # six-high beats the steel wheel
        ("Ah Ad Ac Ks Kd", "Kh Kc Ks Ad Ac"),
        ("Ah 9h 7h 4h 3h", "Ah 9h 7h 4h 2h"),  # fifth flush card decides
        ("6c 5d 4h 3s 2c", "5c 4d 3h 2s Ac"),  # wheel is the lowest straight
        ("Kc Kd 9h 9s 3c", "Kc Kd 9h 9s 2c"),  # two-pair kicker
        ("Ac Ad Kh Qs 4c", "Ac Ad Kh Qs 3c"),
        ("Ac Kd Qh Js 9c", "Ac Kd Qh Js 8c"),
        ("2c 2d 2h 2s 3c", "Ac Ad Ah Ks Kc"),
    ],
)
def test_ordering(better: str, worse: str) -> None:
    assert evaluate(cards(better)) > evaluate(cards(worse))


def test_ties_ignore_suits() -> None:
    assert evaluate(cards("As Kd 9h 7c 3s")) == evaluate(cards("Ah Kc 9d 7s 3h"))


@pytest.mark.parametrize(
    ("hand", "best"),
    [
        ("Ah Kh Qh Jh Th 2c 3d", "Royal flush"),
        ("9c 9d 9h 7s 7c 7d 2h", "Full house, Nines over Sevens"),
        ("9c 9d 9h 9s 7c 7d Ah", "Four Nines"),
        ("2h 3h 4h 5h 7h 6h 8c", "Straight flush, Seven high"),
        ("Ac 2d 3h 4s 5c 9d Kd", "Straight, Five high"),
        ("Kc Kd 9h 9s 3c 3d Ah", "Two pair, Kings and Nines"),
        ("Ah Kh 8h 6h 2h Qh 3c", "Flush, Ace high"),
        ("Ac Ad 7h 6s 2c 9d Th", "Pair of Aces"),
        ("Ac Jd 8h 6s 2c 3d 4h", "Ace high"),
        ("Kc Kd Kh 7s 2c 9d Th", "Three Kings"),
    ],
)
def test_seven_card_hands_and_descriptions(hand: str, best: str) -> None:
    assert describe(evaluate(cards(hand))) == best


def test_two_pair_kicker_can_be_a_third_pair() -> None:
    score = evaluate(cards("Kc Kd 9h 9s 4c 4d 2h"))
    assert score == evaluate(cards("Kc Kd 9h 9s 4c"))


def test_best_five_picks_the_scoring_cards() -> None:
    seven = cards("Ah Kh Qh Jh Th 2c 3d")
    assert sorted(map(str, best_five(seven))) == sorted(["Ah", "Kh", "Qh", "Jh", "Th"])
    assert evaluate(best_five(seven)) == evaluate(seven)


def test_card_count_is_checked() -> None:
    with pytest.raises(ValueError):
        evaluate(cards("As Ks"))


def test_seven_card_score_equals_best_five_card_subset() -> None:
    rng = random.Random(7)
    deck = full_deck()
    for _ in range(1500):
        hand = rng.sample(deck, 7)
        brute = max(evaluate(c) for c in combinations(hand, 5))
        assert evaluate(hand) == brute


@pytest.mark.slow
def test_exhaustive_five_card_category_counts() -> None:
    """Every one of the 2,598,960 five-card hands, against the textbook counts."""
    counts = Counter(category_of(evaluate(h)) for h in combinations(full_deck(), 5))
    assert counts == {
        Category.STRAIGHT_FLUSH: 40,
        Category.FOUR_OF_A_KIND: 624,
        Category.FULL_HOUSE: 3_744,
        Category.FLUSH: 5_108,
        Category.STRAIGHT: 10_200,
        Category.THREE_OF_A_KIND: 54_912,
        Category.TWO_PAIR: 123_552,
        Category.PAIR: 1_098_240,
        Category.HIGH_CARD: 1_302_540,
    }


@pytest.mark.slow
def test_seven_card_category_counts() -> None:
    """Distinct-score check is too big; sample the 7-card frequencies instead."""
    rng = random.Random(1)
    deck = full_deck()
    n = 60_000
    counts = Counter(category_of(evaluate(rng.sample(deck, 7))) for _ in range(n))
    # Known 7-card probabilities (e.g. pair 43.8%, high card 17.4%, two pair 23.5%).
    assert abs(counts[Category.PAIR] / n - 0.438) < 0.01
    assert abs(counts[Category.TWO_PAIR] / n - 0.235) < 0.01
    assert abs(counts[Category.HIGH_CARD] / n - 0.174) < 0.01
    assert abs(counts[Category.FLUSH] / n - 0.0303) < 0.004
