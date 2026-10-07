from __future__ import annotations

import random
from collections import Counter

import pytest

from neon_royale.core.cards import cards
from neon_royale.core.money import dollars
from neon_royale.core.poker import ai
from neon_royale.core.poker.ai import chen_score, decide, equity_job
from neon_royale.core.poker.engine import Acted, Move, PokerError, PokerTable, Seat
from neon_royale.core.poker.room import (
    DEFAULT_BUY_IN,
    HUMAN_SEAT,
    MAX_BUY_IN,
    MIN_BUY_IN,
    PokerRoom,
    RoomError,
)
from neon_royale.core.wallet import Wallet


@pytest.mark.parametrize(
    ("hand", "score"),
    [("As Ah", 20), ("Ks Kd", 16), ("5s 5d", 5), ("2c 2d", 5), ("As Ks", 12), ("Js Ts", 9),
     ("7h 2c", -1), ("Ac Qd", 9), ("9s 8s", 8), ("Kh 7h", 5)],
)  # fmt: skip
def test_chen_scores(hand: str, score: float) -> None:
    assert chen_score(cards(hand)) == score


def run_equity(hole: str, board: str, opponents: int, sims: int = 1500) -> float:
    job = equity_job(cards(hole), cards(board), opponents, random.Random(1), simulations=sims)
    while True:
        try:
            next(job)
        except StopIteration as done:
            return done.value


def test_equity_estimates_are_sensible() -> None:
    assert run_equity("As Ah", "", 1) == pytest.approx(0.85, abs=0.04)
    assert run_equity("7h 2c", "", 1) == pytest.approx(0.35, abs=0.04)
    assert run_equity("As Ah", "", 4) == pytest.approx(0.56, abs=0.05)
    assert run_equity("Ah Kh", "Qh Jh Th", 3, 200) == 1.0, "royal flush can't lose"
    assert run_equity("2c 3d", "", 0) == 1.0


def test_thinking_yields_between_batches() -> None:
    job = equity_job(cards("As Kd"), cards("2c 7h 9s"), 2, random.Random(0), 120, 40)
    yields = 0
    with pytest.raises(StopIteration):
        while True:
            next(job)
            yields += 1
    assert yields == 3


def bots_table(profiles: list[str], seed: int = 0) -> PokerTable:
    seats = [Seat(f"B{i}", dollars(1000), profile=p) for i, p in enumerate(profiles)]
    return PokerTable(seats, rng=random.Random(seed))


def test_bots_only_make_legal_moves_and_conserve_chips() -> None:
    rng = random.Random(4)
    table = bots_table(["rock", "shark", "maniac", "station", "solid", "shark"], seed=8)
    start = sum(s.stack for s in table.seats)
    hands = 0
    while hands < 120 and len(table.occupied()) >= 2:
        table.start_hand()
        hands += 1
        while table.in_hand:
            table.act(decide(table, table.to_act, rng))  # raises PokerError if illegal
    assert sum(s.stack for s in table.seats) == start
    assert hands >= 60


def test_personalities_play_differently() -> None:
    rng = random.Random(11)
    voluntarily = Counter()
    for seed in range(250):
        table = bots_table(["rock", "maniac", "station"], seed=seed)
        events = table.start_hand()
        while table.in_hand:
            events = table.act(decide(table, table.to_act, rng))
            for e in events:
                if isinstance(e, Acted) and e.move in (Move.CALL, Move.RAISE, Move.BET):
                    voluntarily[table.seats[e.seat].profile] += 1
    assert voluntarily["maniac"] > voluntarily["rock"] * 1.5
    assert voluntarily["station"] > voluntarily["rock"]


def test_bots_never_fold_a_free_check() -> None:
    rng = random.Random(2)
    for seed in range(40):
        table = bots_table(["rock", "rock"], seed=seed)
        table.start_hand()
        while table.in_hand:
            legal = table.legal()
            decision = decide(table, table.to_act, rng)
            if legal.can_check:
                assert decision.move is not Move.FOLD
            table.act(decision)


def test_every_roster_profile_exists() -> None:
    assert {p for _, p, _ in ai.ROSTER} <= set(ai.PERSONALITIES)
    assert len({n for n, _, _ in ai.ROSTER}) == len(ai.ROSTER)


# -- the room ---------------------------------------------------------------------------


def test_room_fills_bots_and_seats_the_player() -> None:
    wallet = Wallet(dollars(5_000))
    room = PokerRoom(wallet, random.Random(1))
    assert not room.seated
    assert all(room.table.seats[i] is not None for i in range(1, 6))
    names = [s.name for s in room.table.seats if s]
    assert len(names) == len(set(names))
    room.sit_down(DEFAULT_BUY_IN)
    assert wallet.balance == dollars(4_000)
    assert room.human.is_human and room.table.seats[HUMAN_SEAT] is room.human


def test_buy_in_limits() -> None:
    room = PokerRoom(Wallet(dollars(300)), random.Random(1))
    with pytest.raises(RoomError):
        room.sit_down(MIN_BUY_IN - dollars(1))
    with pytest.raises(RoomError):
        room.sit_down(MAX_BUY_IN + dollars(10))
    with pytest.raises(RoomError, match="not enough"):
        room.sit_down(MIN_BUY_IN)


def test_cash_out_returns_the_stack() -> None:
    wallet = Wallet(dollars(5_000))
    room = PokerRoom(wallet, random.Random(1))
    room.sit_down(dollars(500))
    room.human.stack += dollars(120)  # pretend we won
    assert room.cash_out() == dollars(620)
    assert wallet.balance == dollars(5_120)
    assert not room.seated
    assert room.cash_out() == 0


def test_top_up_between_hands_only() -> None:
    wallet = Wallet(dollars(5_000))
    room = PokerRoom(wallet, random.Random(1))
    room.sit_down(MIN_BUY_IN)
    low, high = room.buy_in_range()
    assert high == MAX_BUY_IN - MIN_BUY_IN
    room.top_up(dollars(100))
    assert room.stack == MIN_BUY_IN + dollars(100)
    room.table.start_hand()
    with pytest.raises(RoomError):
        room.top_up(dollars(100))
    with pytest.raises(RoomError):
        room.cash_out()
    with pytest.raises(RoomError):
        room.fill_seats()
    del low


def test_busted_bots_are_replaced() -> None:
    room = PokerRoom(Wallet(dollars(5_000)), random.Random(3))
    room.table.seats[2].stack = 0
    old = room.table.seats[2]
    assert room.fill_seats() == [2]
    assert room.table.seats[2] is not old and room.table.seats[2].stack > 0


def test_cannot_act_out_of_turn() -> None:
    table = bots_table(["solid", "solid"])
    with pytest.raises(PokerError):
        table.legal()
