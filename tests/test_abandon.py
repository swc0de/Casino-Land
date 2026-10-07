"""Closing the game mid-round never loses chips that were on a table."""

from __future__ import annotations

import random

from neon_royale.core import roulette as r
from neon_royale.core.blackjack import BlackjackTable, Phase
from neon_royale.core.cards import Shoe, cards
from neon_royale.core.money import dollars
from neon_royale.core.poker.engine import Decision, Move
from neon_royale.core.poker.room import PokerRoom
from neon_royale.core.roulette import RouletteTable
from neon_royale.core.wallet import Wallet


def test_roulette_refunds_unspun_bets() -> None:
    table = RouletteTable(Wallet(dollars(100)), random.Random(1))
    table.place(r.red(), dollars(30))
    assert table.abandon() == dollars(30)
    assert table.wallet.balance == dollars(100)


def test_roulette_settles_a_spin_in_progress() -> None:
    table = RouletteTable(Wallet(dollars(100)), random.Random(1))
    table.place(r.straight(17), dollars(10))
    table.spin(17)
    assert table.abandon() == dollars(360)
    assert table.wallet.balance == dollars(450)
    assert table.history == [17]


def test_blackjack_voids_an_unfinished_hand() -> None:
    wallet = Wallet(dollars(100))
    table = BlackjackTable(wallet, shoe=Shoe.stacked(cards("8h 9s 8d 7c 3s Kd")))
    table.deal(dollars(20))
    table.split()
    assert wallet.balance == dollars(60)
    assert table.abandon() == dollars(40)
    assert wallet.balance == dollars(100)
    assert table.phase is Phase.BETTING


def test_blackjack_abandon_when_idle_is_harmless() -> None:
    table = BlackjackTable(Wallet(dollars(100)), random.Random(1))
    assert table.abandon() == 0
    assert table.phase is Phase.BETTING


def test_poker_voids_hand_and_cashes_out() -> None:
    wallet = Wallet(dollars(5_000))
    room = PokerRoom(wallet, random.Random(2))
    room.sit_down(dollars(1_000))
    stacks_before = [s.stack for s in room.table.seats]
    room.table.start_hand()
    while room.table.in_hand and room.table.to_act is not None:
        legal = room.table.legal()
        if legal.can_raise:
            room.table.act(Decision(legal.raise_move, legal.min_to))
            break
        room.table.act(Decision(Move.CALL))
    returned = room.abandon()
    assert returned == dollars(1_000)
    assert wallet.balance == dollars(5_000)
    assert [s.stack if s else None for s in room.table.seats][1:] == stacks_before[1:]
    assert not room.table.in_hand and not room.seated
