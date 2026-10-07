"""Blackjack rules, driven by stacked shoes.

Deal order is player, dealer up, player, dealer hole; later cards follow in order.
"""

from __future__ import annotations

import random

import pytest

from neon_royale.core.blackjack import (
    MAX_HANDS,
    Action,
    BlackjackTable,
    CardDealt,
    Doubled,
    Hand,
    HandSettled,
    HoleRevealed,
    InsuranceOffered,
    InsuranceSettled,
    Outcome,
    Peeked,
    Phase,
    RoundOver,
    RuleError,
    Shuffled,
    Split,
    TurnChanged,
    basic_strategy,
    hand_value,
)
from neon_royale.core.cards import Card, Shoe, cards
from neon_royale.core.money import dollars
from neon_royale.core.wallet import Wallet


def table(deck: str, balance: float = 1_000) -> BlackjackTable:
    return BlackjackTable(Wallet(dollars(balance)), shoe=Shoe.stacked(deck.split()))


def outcomes(events) -> list[Outcome]:
    return [e.outcome for e in events if isinstance(e, HandSettled)]


def round_over(events) -> RoundOver:
    return next(e for e in events if isinstance(e, RoundOver))


@pytest.mark.parametrize(
    ("hand", "total", "soft"),
    [
        ("As Kd", 21, True),
        ("As 6d", 17, True),
        ("As 6d Kh", 17, False),
        ("As Ad", 12, True),
        ("As Ad 9h", 21, True),
        ("As Ad 9h Kc", 21, False),
        ("Th 6s", 16, False),
        ("5h 5s Ad Ac Ah", 13, False),
    ],
)
def test_hand_value(hand: str, total: int, soft: bool) -> None:
    assert hand_value(cards(hand)) == (total, soft)


def test_simple_win_pays_even_money() -> None:
    t = table("Kh Ts Qd 8c")
    events = t.deal(dollars(10))
    assert [e.face_up for e in events if isinstance(e, CardDealt)] == [True, True, True, False]
    assert t.phase is Phase.PLAYER
    assert t.dealer_total == 10, "hole card is hidden"
    events = t.stand()
    assert isinstance(events[0], HoleRevealed)
    assert outcomes(events) == [Outcome.WIN]
    assert t.wallet.balance == dollars(1_010)
    assert round_over(events).net == dollars(10)
    assert t.phase is Phase.SETTLED


@pytest.mark.parametrize(
    ("bet", "paid"), [(dollars(10), dollars(25)), (dollars(15), dollars(37.5))]
)
def test_blackjack_pays_three_to_two(bet: int, paid: int) -> None:
    t = table("As 9h Kd 7c")
    events = t.deal(bet)
    assert t.phase is Phase.SETTLED
    assert outcomes(events) == [Outcome.BLACKJACK]
    assert round_over(events).returned == paid


def test_dealer_stands_on_soft_17() -> None:
    t = table("Th 6s 9d Ac")
    t.deal(dollars(10))
    events = t.stand()
    assert not [e for e in events if isinstance(e, CardDealt)], "dealer must not draw"
    assert outcomes(events) == [Outcome.WIN]


def test_dealer_hits_soft_16_and_hard_16() -> None:
    t = table("Th 5s 9d Ac 2h")  # dealer A5 = soft 16 -> draws 2 -> 18
    t.deal(dollars(10))
    events = t.stand()
    assert outcomes(events) == [Outcome.WIN]
    assert hand_value(t.dealer)[0] == 18

    t = table("Th Ts 7d 6c 5h")  # dealer T6 -> draws 5 -> 21
    t.deal(dollars(10))
    assert outcomes(t.stand()) == [Outcome.LOSE]


def test_push_returns_the_stake() -> None:
    t = table("Th Ts 8d 8c")
    t.deal(dollars(10))
    events = t.stand()
    assert outcomes(events) == [Outcome.PUSH]
    assert t.wallet.balance == dollars(1_000)


def test_dealer_peeks_with_ten_up() -> None:
    t = table("9h Ks 8d Ac")
    events = t.deal(dollars(10))
    assert Peeked(True) in events
    assert t.phase is Phase.SETTLED
    assert outcomes(events) == [Outcome.LOSE]
    assert t.wallet.balance == dollars(990)


def test_peek_without_blackjack_continues() -> None:
    t = table("9h Ks 8d 7c")
    events = t.deal(dollars(10))
    assert Peeked(False) in events
    assert t.phase is Phase.PLAYER
    assert t.hole_hidden


def test_both_blackjacks_push() -> None:
    t = table("Ah Ks Kd Ac")
    events = t.deal(dollars(10))
    assert outcomes(events) == [Outcome.PUSH]
    assert t.wallet.balance == dollars(1_000)


def test_insurance_pays_two_to_one_on_dealer_blackjack() -> None:
    t = table("Th As 9d Kc")
    events = t.deal(dollars(10))
    assert events[-1] == InsuranceOffered(dollars(5))
    assert t.phase is Phase.INSURANCE
    with pytest.raises(RuleError):
        t.hit()
    events = t.take_insurance()
    kinds = [type(e).__name__ for e in events]
    assert kinds.index("InsuranceSettled") < kinds.index("HandSettled")
    assert InsuranceSettled(dollars(5), dollars(15)) in events
    assert outcomes(events) == [Outcome.LOSE]
    summary = round_over(events)
    assert summary.wagered == dollars(15) and summary.returned == dollars(15)
    assert t.wallet.balance == dollars(1_000)


def test_declined_insurance_then_play_on() -> None:
    t = table("Th As 9d 7c")
    t.deal(dollars(10))
    events = t.decline_insurance()
    assert events == [Peeked(False), TurnChanged(0)]
    assert t.phase is Phase.PLAYER


def test_lost_insurance_without_dealer_blackjack() -> None:
    t = table("Th As 9d 7c")
    t.deal(dollars(10))
    events = t.take_insurance(dollars(2))
    assert InsuranceSettled(dollars(2), 0) in events
    assert t.wallet.balance == dollars(988)
    with pytest.raises(RuleError):
        t.take_insurance()


def test_even_money_is_insurance_on_a_blackjack() -> None:
    t = table("Ah As Kd 7c")
    t.deal(dollars(10))
    events = t.take_insurance()
    assert outcomes(events) == [Outcome.BLACKJACK]
    assert t.wallet.balance == dollars(1_010), "even money: +1x the bet either way"


def test_insurance_limits() -> None:
    t = table("Th As 9d 7c")
    t.deal(dollars(10))
    with pytest.raises(RuleError):
        t.take_insurance(dollars(6))


def test_double_down() -> None:
    t = table("5h 6s 6d Tc Th 9s")
    t.deal(dollars(10))
    assert Action.DOUBLE in t.legal_actions()
    events = t.double()
    assert Doubled(0, dollars(20)) in events
    hand = t.hands[0]
    assert hand.total == 21 and len(hand.cards) == 3
    assert outcomes(events) == [Outcome.WIN], "dealer 16 draws 9 and busts"
    assert t.wallet.balance == dollars(1_020)


def test_double_only_on_two_cards_and_if_affordable() -> None:
    t = table("2h 6s 3d Tc 2c 9s 9h")
    t.deal(dollars(10))
    t.hit()
    assert Action.DOUBLE not in t.legal_actions()

    poor = table("5h 6s 6d Tc", balance=15)
    poor.deal(dollars(10))
    assert Action.DOUBLE not in poor.legal_actions()


def test_split_eights_plays_each_hand() -> None:
    t = table("8h 9s 8d 7c Ts Kd 5c")
    t.deal(dollars(10))
    events = t.split()
    assert events[0] == Split(0, 1)
    assert len(t.hands) == 2 and t.active == 0
    assert [str(c) for c in t.hands[0].cards] == ["8h", "Ts"]
    assert len(t.hands[1].cards) == 1, "second hand waits for its card"
    assert t.wallet.balance == dollars(980)

    events = t.stand()
    assert TurnChanged(1) in events
    assert [str(c) for c in t.hands[1].cards] == ["8d", "Kd"]
    events = t.stand()
    assert outcomes(events) == [Outcome.LOSE, Outcome.LOSE]  # dealer 16 + 5 = 21
    assert t.wallet.balance == dollars(980)


def test_split_aces_get_one_card_and_21_is_not_blackjack() -> None:
    t = table("Ah 9s Ad 7c Kh 5d Tc")
    t.deal(dollars(10))
    events = t.split()
    assert t.phase is Phase.SETTLED, "both ace hands are complete"
    assert [len(h.cards) for h in t.hands] == [2, 2]
    assert outcomes(events) == [Outcome.WIN, Outcome.WIN]
    assert round_over(events).returned == dollars(40)


def test_cannot_resplit_aces() -> None:
    t = table("Ah 9s Ad 7c Ac 5d Tc")
    t.deal(dollars(10))
    t.split()
    assert t.phase is Phase.SETTLED


def test_resplit_up_to_four_hands_and_double_after_split() -> None:
    t = table("8h 9s 8d 7c 8s 8c 3h Th 2d 2c Ts 9h 9d")
    t.deal(dollars(10))
    t.split()  # hand0: 8 8s
    t.split()  # hand0: 8 8c, hand1: 8s
    t.split()  # hand0: 8 3h, hands: 8h3h | 8c | 8s | 8d
    assert len(t.hands) == MAX_HANDS
    assert Action.SPLIT not in t.legal_actions()
    assert Action.DOUBLE in t.legal_actions(), "double after split"
    t.double()  # 8 3 T = 21
    assert t.active == 1
    for _ in range(3):
        t.stand()
    assert t.phase is Phase.SETTLED
    assert sum(h.bet for h in t.hands) == dollars(50)


def test_equal_value_tens_can_be_split() -> None:
    t = table("Kh 9s Qd 7c")
    t.deal(dollars(10))
    assert Action.SPLIT in t.legal_actions()


def test_late_surrender_returns_half() -> None:
    t = table("Th Ts 6d 7c")
    t.deal(dollars(10))
    assert Action.SURRENDER in t.legal_actions()
    events = t.surrender()
    assert outcomes(events) == [Outcome.SURRENDER]
    assert not [e for e in events if isinstance(e, CardDealt)], "dealer doesn't play"
    assert t.wallet.balance == dollars(995)


def test_no_surrender_after_hitting_or_splitting() -> None:
    t = table("2h Ts 3d 7c 2c 4h")
    t.deal(dollars(10))
    t.hit()
    assert Action.SURRENDER not in t.legal_actions()

    t = table("8h Ts 8d 7c 2c 4h")
    t.deal(dollars(10))
    t.split()
    assert Action.SURRENDER not in t.legal_actions()


def test_bust_loses_without_dealer_drawing() -> None:
    t = table("Th 9s 6d 7c Kh")
    t.deal(dollars(10))
    events = t.hit()
    assert outcomes(events) == [Outcome.BUST]
    assert not [e for e in events if isinstance(e, CardDealt) and e.to == "dealer"]


def test_hitting_to_21_stands_automatically() -> None:
    t = table("5h 9s 6d 7c Th 2c")
    t.deal(dollars(10))
    events = t.hit()
    assert t.phase is Phase.SETTLED
    assert outcomes(events) == [Outcome.WIN]


@pytest.mark.parametrize("bet", [dollars(4), dollars(5_001), 550])
def test_bet_limits(bet: int) -> None:
    with pytest.raises(RuleError):
        table("Kh Ts Qd 8c").deal(bet)


def test_insufficient_funds() -> None:
    with pytest.raises(RuleError, match="chips"):
        table("Kh Ts Qd 8c", balance=8).deal(dollars(10))


def test_phases_are_enforced() -> None:
    t = table("Kh Ts Qd 8c Kh Ts Qd 8c")
    with pytest.raises(RuleError):
        t.stand()
    t.deal(dollars(10))
    with pytest.raises(RuleError):
        t.deal(dollars(10))
    t.stand()
    with pytest.raises(RuleError):
        t.deal(dollars(10))
    t.new_round()
    assert t.phase is Phase.BETTING and t.hands == []
    t.deal(dollars(10))


def test_reshuffles_at_the_cut_card() -> None:
    t = BlackjackTable(Wallet(dollars(100_000)), random.Random(1))
    shuffles = 0
    for _ in range(200):
        events = t.deal(dollars(5))
        shuffles += sum(isinstance(e, Shuffled) for e in events)
        while t.phase is Phase.INSURANCE:
            events = t.decline_insurance()
        while t.phase is Phase.PLAYER:
            t.stand()
        t.new_round()
    assert shuffles >= 2


# -- strategy -------------------------------------------------------------------------

ALL = {Action.HIT, Action.STAND, Action.DOUBLE, Action.SPLIT, Action.SURRENDER}


@pytest.mark.parametrize(
    ("hand", "up", "action"),
    [
        ("Th 7d", "Ah", Action.STAND),
        ("Th 6d", "Th", Action.SURRENDER),
        ("Th 6d", "7h", Action.HIT),
        ("Th 2d", "3h", Action.HIT),
        ("Th 2d", "4h", Action.STAND),
        ("6h 5d", "Th", Action.DOUBLE),
        ("6h 5d", "Ah", Action.HIT),
        ("As 7d", "3h", Action.DOUBLE),
        ("As 7d", "8h", Action.STAND),
        ("As 7d", "9h", Action.HIT),
        ("8s 8d", "Ah", Action.SPLIT),
        ("Ts Td", "6h", Action.STAND),
        ("9s 9d", "7h", Action.STAND),
        ("5s 5d", "9h", Action.DOUBLE),
        ("As Ad", "Th", Action.SPLIT),
    ],
)
def test_basic_strategy(hand: str, up: str, action: Action) -> None:
    assert basic_strategy(Hand(cards(hand)), Card.parse(up), ALL) == action


def test_strategy_falls_back_when_options_are_missing() -> None:
    no_extras = {Action.HIT, Action.STAND}
    assert basic_strategy(Hand(cards("As 7d")), Card.parse("4h"), no_extras) == Action.STAND
    assert basic_strategy(Hand(cards("6h 5d")), Card.parse("Th"), no_extras) == Action.HIT
    assert basic_strategy(Hand(cards("Th 6d")), Card.parse("Th"), no_extras) == Action.HIT
    assert basic_strategy(Hand(cards("As Ad")), Card.parse("6h"), no_extras) == Action.HIT


def _play_round(t: BlackjackTable, bet: int) -> int:
    before = t.wallet.balance
    summary = None
    events = t.deal(bet)
    while True:
        summary = next((e for e in events if isinstance(e, RoundOver)), summary)
        if t.phase is Phase.INSURANCE:
            events = t.decline_insurance()
        elif t.phase is Phase.PLAYER:
            events = t.act(basic_strategy(t.hand, t.upcard, t.legal_actions()))
        else:
            break
    assert summary is not None
    assert t.wallet.balance - before == summary.net, "wallet moves exactly by the round's net"
    t.new_round()
    return summary.net


def test_long_run_with_basic_strategy_is_close_to_even() -> None:
    t = BlackjackTable(Wallet(dollars(10_000_000)), random.Random(2024))
    rounds = 20_000
    net = sum(_play_round(t, dollars(10)) for _ in range(rounds))
    edge = net / (rounds * dollars(10))
    # True house edge for these rules is about -0.3%; allow for sampling noise.
    assert -0.035 < edge < 0.025
