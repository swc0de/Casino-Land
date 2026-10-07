from __future__ import annotations

import random

import pytest

from neon_royale.core.cards import cards
from neon_royale.core.money import dollars
from neon_royale.core.poker.engine import (
    Acted,
    BlindPosted,
    BoardDealt,
    Decision,
    HandOver,
    HandStarted,
    Move,
    PokerError,
    PokerTable,
    PotAwarded,
    Seat,
    Showdown,
    Street,
    UncalledReturned,
    build_pots,
)

FOLD = Decision(Move.FOLD)
CHECK = Decision(Move.CHECK)
CALL = Decision(Move.CALL)


def raise_to(amount: float) -> Decision:
    return Decision(Move.RAISE, dollars(amount))


def bet(amount: float) -> Decision:
    return Decision(Move.BET, dollars(amount))


def make(stacks: list[float], button: int | None = None) -> PokerTable:
    seats = [Seat(f"P{i}", dollars(s)) for i, s in enumerate(stacks)]
    # ``button`` is where the button *was*; start_hand moves it one seat on.
    return PokerTable(seats, dollars(5), dollars(10), random.Random(3), button=button)


def total_chips(table: PokerTable) -> int:
    return sum(s.stack for s in table.seats if s) + table.total_pot


def awards(events) -> list[PotAwarded]:
    return [e for e in events if isinstance(e, PotAwarded)]


# -- blinds and order -------------------------------------------------------------------


def test_three_handed_blinds_and_first_to_act() -> None:
    t = make([1000, 1000, 1000], button=2)  # button moves to seat 0
    events = t.start_hand()
    started = events[0]
    assert isinstance(started, HandStarted)
    assert (started.button, started.small_blind, started.big_blind) == (0, 1, 2)
    blinds = [e for e in events if isinstance(e, BlindPosted)]
    assert [(b.seat, b.amount) for b in blinds] == [(1, dollars(5)), (2, dollars(10))]
    assert t.to_act == 0, "under the gun is left of the big blind"


def test_heads_up_button_posts_small_blind_and_acts_first_preflop_only() -> None:
    t = make([1000, 1000], button=1)
    events = t.start_hand()
    assert (events[0].button, events[0].small_blind, events[0].big_blind) == (0, 0, 1)
    assert t.to_act == 0, "button acts first pre-flop"
    t.act(CALL)
    assert t.to_act == 1, "big blind has the option"
    events = t.act(CHECK)
    assert any(isinstance(e, BoardDealt) for e in events)
    assert t.to_act == 1, "big blind acts first after the flop"


def test_button_moves_each_hand() -> None:
    t = make([1000, 1000, 1000], button=2)
    t.start_hand()
    while t.in_hand:
        t.act(FOLD)
    t.start_hand()
    assert t.button == 1


def test_big_blind_option_to_raise_when_limped_to() -> None:
    t = make([1000, 1000, 1000], button=2)
    t.start_hand()
    t.act(CALL)
    t.act(CALL)
    legal = t.legal()
    assert t.to_act == 2
    assert legal.can_check and legal.can_raise
    assert legal.min_to == dollars(20)


# -- raising rules ----------------------------------------------------------------------


def test_minimum_raise_is_the_last_raise_size() -> None:
    t = make([1000, 1000, 1000], button=2)
    t.start_hand()
    assert t.legal().min_to == dollars(20)
    with pytest.raises(PokerError):
        t.act(raise_to(15))
    t.act(raise_to(35))  # raise of 25
    assert t.legal().min_to == dollars(60)
    with pytest.raises(PokerError):
        t.act(raise_to(55))
    t.act(raise_to(60))
    assert t.legal().min_to == dollars(85)


def test_bets_must_be_whole_dollars_and_within_stack() -> None:
    t = make([1000, 1000], button=1)
    t.start_hand()
    with pytest.raises(PokerError):
        t.act(Decision(Move.RAISE, dollars(30) + 50))
    with pytest.raises(PokerError):
        t.act(raise_to(2000))
    with pytest.raises(PokerError):
        t.act(CHECK)


def test_short_all_in_does_not_reopen_betting() -> None:
    # Seat 0 raises to 100; seat 1 goes all-in for 140 (a raise of only 40);
    # seat 0 already acted and may only call or fold.
    t = make([1000, 140, 1000], button=2)
    t.start_hand()  # button 0, sb 1, bb 2; seat 0 acts first
    t.act(raise_to(100))
    t.act(raise_to(140))  # all-in short raise from the small blind
    legal = t.legal()
    assert t.to_act == 2, "big blind hasn't acted yet and may re-raise"
    assert legal.can_raise
    t.act(CALL)
    legal = t.legal()
    assert t.to_act == 0
    assert not legal.can_raise, "action wasn't reopened for seat 0"
    assert legal.to_call == dollars(40)


def test_full_raise_after_all_in_reopens() -> None:
    t = make([1000, 140, 1000], button=2)
    t.start_hand()
    t.act(raise_to(100))
    t.act(raise_to(140))
    t.act(raise_to(300))  # big blind makes a full raise
    assert t.to_act == 0
    assert t.legal().can_raise


def test_cannot_raise_when_everyone_else_is_all_in() -> None:
    t = make([1000, 50], button=1)
    t.start_hand()
    t.act(raise_to(1000))  # button shoves
    legal = t.legal()
    assert legal.to_call == dollars(40) and not legal.can_raise
    events = t.act(CALL)
    assert isinstance(events[-1], HandOver)
    assert any(isinstance(e, UncalledReturned) and e.amount == dollars(950) for e in events)
    assert sum(s.stack for s in t.seats) == dollars(1050)


def test_fold_turns_into_check_when_free() -> None:
    t = make([1000, 1000], button=1)
    t.start_hand()
    t.act(CALL)
    events = t.act(FOLD)
    assert isinstance(events[0], Acted) and events[0].move is Move.CHECK


# -- winning pots -----------------------------------------------------------------------


def test_everyone_folds_to_the_big_blind() -> None:
    t = make([1000, 1000, 1000], button=2)
    t.start_hand()
    t.act(FOLD)
    events = t.act(FOLD)
    won = awards(events)
    # The big blind's unmatched $5 goes back first, so the pot actually won is $10.
    assert UncalledReturned(2, dollars(5)) in events
    assert len(won) == 1 and won[0].winners == (2,) and won[0].amount == dollars(10)
    assert won[0].description == ""
    assert [s.stack for s in t.seats] == [dollars(1000), dollars(995), dollars(1005)]
    assert events[-1].net == (0, -dollars(5), dollars(5))
    assert not t.in_hand


def test_uncalled_bet_is_returned() -> None:
    t = make([1000, 1000], button=1)
    t.start_hand()
    t.act(raise_to(300))
    events = t.act(FOLD)
    assert UncalledReturned(0, dollars(290)) in events
    assert t.seats[0].stack == dollars(1010)


def deal_order(holes: list[str], board: str) -> list:
    """Stacked deck for a hand dealt starting at the small blind."""
    first = [h.split()[0] for h in holes]
    second = [h.split()[1] for h in holes]
    b = board.split()
    burn = "2c"
    order = first + second + [burn, *b[:3], burn, b[3], burn, b[4]]
    return cards(" ".join(order))


def test_showdown_best_hand_wins() -> None:
    t = make([1000, 1000], button=1)
    # heads-up: seat 0 is button/sb and is dealt first
    t.stack_deck(deal_order(["Ah Kh", "Qs Qd"], "Ad 7c 2s 9h 3d"))
    t.start_hand()
    t.act(CALL)
    events = t.act(CHECK)
    for _ in range(3):
        events = t.act(CHECK)
        events = t.act(CHECK)
    show = next(e for e in events if isinstance(e, Showdown))
    assert {h.seat for h in show.hands} == {0, 1}
    won = awards(events)[0]
    assert won.winners == (0,) and won.description == "Pair of Aces"
    assert t.seats[0].stack == dollars(1010)


def test_split_pot_odd_chip() -> None:
    t = make([1000, 1000, 1000], button=2)
    t.stack_deck(deal_order(["2h 3h", "4d 2d", "4c 3c"], "Ts Js Qd Kc Ah"))
    t.start_hand()  # button 0, sb 1, bb 2
    t.act(FOLD)  # seat 0 folds
    t.act(CALL)  # sb completes: pot 20
    t.act(raise_to(15 + 10))  # bb raises to 25
    events = t.act(CALL)  # pot 50
    # make the pot odd: sb bets 1 on the flop? whole dollars only, so use 5 + call
    for _ in range(3):
        events = t.act(CHECK)
        events = t.act(CHECK)
    won = awards(events)[0]
    assert won.amount == dollars(50) and sorted(won.winners) == [1, 2]
    assert won.shares == (dollars(25), dollars(25))


def test_three_way_split_gives_odd_chip_left_of_button() -> None:
    t = make([1000, 1000, 1000, 1000], button=3)
    # button 0, sb 1, bb 2, utg 3; the board is a royal flush everyone plays.
    t.stack_deck(deal_order(["2h 3d", "4h 5d", "6h 7d", "8h 9d"], "Ts Js Qs Ks As"))
    t.start_hand()
    t.act(CALL)  # utg
    t.act(CALL)  # button
    t.act(CALL)  # sb completes
    t.act(CHECK)  # bb: pot $40
    t.act(bet(10))  # sb bets the minimum on the flop
    t.act(CALL)  # bb
    t.act(CALL)  # utg
    t.act(FOLD)  # button folds: pot $70
    events = []
    for _ in range(2):
        for _ in range(3):
            events = t.act(CHECK)
    won = awards(events)[0]
    assert won.amount == dollars(70)
    assert won.winners == (1, 2, 3), "ordered clockwise from the button"
    assert won.shares == (dollars(24), dollars(23), dollars(23))


def test_postflop_minimum_bet_is_the_big_blind() -> None:
    t = make([1000, 1000], button=1)
    t.start_hand()
    t.act(CALL)
    t.act(CHECK)
    assert t.legal().min_to == dollars(10)
    with pytest.raises(PokerError):
        t.act(bet(5))


def test_side_pots_with_multiple_all_ins() -> None:
    t = make([1000, 100, 300, 1000], button=3)
    # button 0, sb 1 (100), bb 2 (300), utg 3. Seat 1 has the nuts, seat 2 second best.
    t.stack_deck(
        deal_order(["Ac Ad", "Kc Kd", "Qc Qd", "2s 7h"], "Ah Kh 3c 8s 9d")
    )  # deal order starts at sb: seat1, seat2, seat3, seat0
    t.start_hand()
    t.act(raise_to(1000))  # utg (3) shoves
    t.act(CALL)  # button (0) calls all-in
    t.act(CALL)  # sb (1) calls all-in for 100
    events = t.act(CALL)  # bb (2) calls all-in for 300
    assert isinstance(events[-1], HandOver)
    won = awards(events)
    # main pot 4x100 to seat 1 (aces full? trips aces), side pot 3x200 to seat 2 (trip kings),
    # last side pot 2x700 between seats 0 and 3: seat 3 (queens) beats 7-high.
    assert [(w.amount, w.winners) for w in won] == [
        (dollars(400), (1,)),
        (dollars(600), (2,)),
        (dollars(1400), (3,)),
    ]
    assert [s.stack for s in t.seats] == [0, dollars(400), dollars(600), dollars(1400)]


def test_build_pots_merges_and_handles_folds() -> None:
    pots = build_pots({0: 50, 1: 100, 2: 100, 3: 30}, live={0, 1, 2})
    assert [(p.amount, p.eligible) for p in pots] == [(180, [0, 1, 2]), (100, [1, 2])]
    pots = build_pots({0: 100, 1: 100, 2: 40}, live={0, 1})
    assert [(p.amount, p.eligible) for p in pots] == [(240, [0, 1])]


def test_all_in_preflop_runs_the_board_out() -> None:
    t = make([500, 500], button=1)
    t.start_hand()
    t.act(raise_to(500))
    events = t.act(CALL)
    boards = [e for e in events if isinstance(e, BoardDealt)]
    assert [b.street for b in boards] == [Street.FLOP, Street.TURN, Street.RIVER]
    assert len(t.board) == 5
    assert sum(s.stack for s in t.seats) == dollars(1000)


def test_short_big_blind_still_sets_the_price() -> None:
    t = make([1000, 1000, 4], button=2)
    events = t.start_hand()
    bb = next(e for e in events if isinstance(e, BlindPosted) and e.kind == "big")
    assert bb.amount == dollars(4) and bb.all_in
    assert t.legal().to_call == dollars(10)


def test_needs_two_players() -> None:
    t = make([1000, 0])
    with pytest.raises(PokerError):
        t.start_hand()
    t = make([1000, 1000], button=1)
    t.start_hand()
    with pytest.raises(PokerError):
        t.start_hand()


def test_random_hands_conserve_chips() -> None:
    rng = random.Random(99)
    t = PokerTable(
        [Seat(f"P{i}", dollars(rng.randint(200, 2000))) for i in range(6)],
        rng=random.Random(5),
    )
    start = sum(s.stack for s in t.seats)
    hands = 0
    while hands < 400 and len(t.occupied()) >= 2:
        t.start_hand()
        hands += 1
        while t.in_hand:
            assert total_chips(t) == start
            legal = t.legal()
            roll = rng.random()
            if roll < 0.2:
                t.act(FOLD)
            elif roll < 0.65 or not legal.can_raise:
                t.act(CALL)
            else:
                top = min(legal.max_to, legal.min_to * 3)
                target = rng.randint(legal.min_to // 100, top // 100) * 100
                t.act(Decision(legal.raise_move, target))
        assert sum(s.stack for s in t.seats) == start
    assert hands > 50
