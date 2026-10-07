"""No-Limit Texas Hold'em table engine.

Implements cash-game rules for up to ten seats:

* The button moves one occupied seat clockwise each hand. With three or more players
  the small blind sits left of the button; heads-up, the button posts the small blind,
  acts first before the flop and last after it.
* A short big blind still sets the full big blind as the amount to call.
* A raise must be at least the size of the previous bet or raise on that street. An
  all-in for less is allowed but does not reopen the betting for players who have
  already acted; they may only call or fold.
* An uncalled bet is returned. Pots are split into a main pot and side pots by
  contribution; split pots go to the tied hands, odd chips to the first winner
  clockwise from the button.

All amounts are integer cents, and bets are made in whole dollars (``CHIP``).
Every action returns events describing what happened for the screen to animate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from ..cards import Card, Shoe
from ..money import Cents, dollars
from .evaluator import best_five, describe, evaluate

CHIP: Cents = dollars(1)  # smallest betting unit at the poker table
DEFAULT_SMALL_BLIND: Cents = dollars(5)
DEFAULT_BIG_BLIND: Cents = dollars(10)


class Street(Enum):
    PREFLOP = "Pre-flop"
    FLOP = "Flop"
    TURN = "Turn"
    RIVER = "River"
    SHOWDOWN = "Showdown"


class Move(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"


@dataclass(frozen=True)
class Decision:
    """What a player chooses. ``amount`` is the total to have in front for BET/RAISE."""

    move: Move
    amount: Cents = 0


@dataclass
class Seat:
    name: str
    stack: Cents
    is_human: bool = False
    profile: str = "solid"
    color: tuple[int, int, int] = (200, 200, 200)


@dataclass
class PlayerState:
    seat: int
    cards: list[Card] = field(default_factory=list)
    bet: Cents = 0  # in front of the player this street
    committed: Cents = 0  # total put in this hand
    folded: bool = False
    all_in: bool = False
    acted_level: int | None = None  # betting level when they last acted this street

    @property
    def live(self) -> bool:
        return not self.folded

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in


# -- events ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandStarted:
    number: int
    button: int
    small_blind: int
    big_blind: int
    seats: tuple[int, ...]


@dataclass(frozen=True)
class BlindPosted:
    seat: int
    amount: Cents
    kind: str  # "small" or "big"
    all_in: bool


@dataclass(frozen=True)
class HoleCards:
    seat: int
    cards: tuple[Card, Card]


@dataclass(frozen=True)
class Acted:
    seat: int
    move: Move
    bet: Cents  # what the player now has in front this street
    added: Cents  # chips moved from stack this action
    all_in: bool


@dataclass(frozen=True)
class ToAct:
    seat: int


@dataclass(frozen=True)
class BetsCollected:
    pot: Cents


@dataclass(frozen=True)
class UncalledReturned:
    seat: int
    amount: Cents


@dataclass(frozen=True)
class BoardDealt:
    street: Street
    cards: tuple[Card, ...]


@dataclass(frozen=True)
class ShowdownHand:
    seat: int
    cards: tuple[Card, Card]
    score: int
    description: str
    best: tuple[Card, ...]


@dataclass(frozen=True)
class Showdown:
    hands: tuple[ShowdownHand, ...]


@dataclass(frozen=True)
class PotAwarded:
    index: int  # 0 = main pot, 1.. = side pots
    amount: Cents
    winners: tuple[int, ...]
    shares: tuple[Cents, ...]
    description: str  # winning hand, or "" when everyone else folded


@dataclass(frozen=True)
class HandOver:
    stacks: tuple[Cents, ...]
    net: tuple[Cents, ...]  # per seat, chips won minus chips put in


Event = (
    HandStarted
    | BlindPosted
    | HoleCards
    | Acted
    | ToAct
    | BetsCollected
    | UncalledReturned
    | BoardDealt
    | Showdown
    | PotAwarded
    | HandOver
)


@dataclass(frozen=True)
class Legal:
    """What the player to act may do."""

    seat: int
    to_call: Cents  # chips needed to call (0 means check is allowed)
    can_check: bool
    can_raise: bool
    min_to: Cents  # smallest legal bet/raise total (may equal max_to for an all-in)
    max_to: Cents  # all-in total
    current_bet: Cents
    pot: Cents  # chips in the middle plus all bets in front

    @property
    def raise_move(self) -> Move:
        return Move.RAISE if self.current_bet > 0 else Move.BET


class PokerError(Exception):
    pass


@dataclass
class Pot:
    amount: Cents
    eligible: list[int]


def build_pots(committed: dict[int, Cents], live: set[int]) -> list[Pot]:
    """Split contributions into main and side pots.

    ``committed`` maps seat -> chips put in this hand (folded players included);
    ``live`` are the seats still contesting. Adjacent levels with the same eligible
    players are merged into one pot.
    """
    levels = sorted({c for s, c in committed.items() if c > 0 and s in live})
    pots: list[Pot] = []
    previous = 0
    for level in levels:
        amount = sum(min(c, level) - min(c, previous) for c in committed.values())
        eligible = sorted(s for s in live if committed[s] >= level)
        if pots and pots[-1].eligible == eligible:
            pots[-1].amount += amount
        elif amount:
            pots.append(Pot(amount, eligible))
        previous = level
    # Folded players' chips above the top live level (only possible as dead money
    # from an uncalled-then-folded edge) join the last pot.
    leftover = sum(max(0, c - previous) for c in committed.values())
    if leftover and pots:
        pots[-1].amount += leftover
    return pots


class PokerTable:
    def __init__(
        self,
        seats: list[Seat | None],
        small_blind: Cents = DEFAULT_SMALL_BLIND,
        big_blind: Cents = DEFAULT_BIG_BLIND,
        rng: random.Random | None = None,
        button: int | None = None,
    ) -> None:
        if small_blind % CHIP or big_blind % CHIP:
            raise ValueError("blinds must be whole dollars")
        self.seats = seats
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.rng = rng or random.Random()
        self.deck = Shoe(1, self.rng)
        self.button = button if button is not None else -1
        self.hand_number = 0
        self.players: dict[int, PlayerState] = {}
        self.board: list[Card] = []
        self.street = Street.SHOWDOWN
        self.to_act: int | None = None
        self.current_bet: Cents = 0
        self.min_raise: Cents = big_blind
        self.reopen_level = 0  # bumped on every full bet or raise
        self.pot: Cents = 0  # chips already gathered into the middle
        self.in_hand = False
        self._starting: dict[int, Cents] = {}
        self._stacked_deck: list[Card] | None = None

    # -- seating --------------------------------------------------------------------------

    def occupied(self) -> list[int]:
        """Seats with a player who has chips, in seat order."""
        return [i for i, s in enumerate(self.seats) if s is not None and s.stack > 0]

    def _next(self, seat: int, among: list[int]) -> int:
        n = len(self.seats)
        for step in range(1, n + 1):
            candidate = (seat + step) % n
            if candidate in among:
                return candidate
        raise PokerError("no seat found")

    def stack_deck(self, order: list[Card]) -> None:
        """Deal the next hand from ``order`` (tests): holes in deal order, then board."""
        self._stacked_deck = list(order)

    # -- hand setup -----------------------------------------------------------------------

    def start_hand(self) -> list[Event]:
        if self.in_hand:
            raise PokerError("a hand is already running")
        active = self.occupied()
        if len(active) < 2:
            raise PokerError("need two players with chips")
        self.hand_number += 1
        self.button = self._next(self.button, active)
        # Heads-up the button posts the small blind; otherwise it's the next seat.
        sb = self.button if len(active) == 2 else self._next(self.button, active)
        bb = self._next(sb, active)

        self.players = {s: PlayerState(s) for s in active}
        self._starting = {s: self.seats[s].stack for s in active}
        self.board = []
        self.pot = 0
        self.street = Street.PREFLOP
        self.in_hand = True
        if self._stacked_deck is not None:
            self.deck = Shoe.stacked(self._stacked_deck)
            self._stacked_deck = None
        else:
            self.deck = Shoe(1, self.rng)

        events: list[Event] = [HandStarted(self.hand_number, self.button, sb, bb, tuple(active))]
        events.append(self._post(sb, self.small_blind, "small"))
        events.append(self._post(bb, self.big_blind, "big"))
        self.current_bet = self.big_blind
        self.min_raise = self.big_blind
        self.reopen_level = 1

        # Deal two cards to each player, one at a time, starting left of the button.
        order = [sb]
        while len(order) < len(active):
            order.append(self._next(order[-1], active))
        for _ in range(2):
            for seat in order:
                self.players[seat].cards.append(self.deck.draw())
        for seat in order:
            c = self.players[seat].cards
            events.append(HoleCards(seat, (c[0], c[1])))

        first = self._next(bb, active)
        return events + self._continue(first)

    def _post(self, seat: int, amount: Cents, kind: str) -> BlindPosted:
        player = self.players[seat]
        paid = min(amount, self.seats[seat].stack)
        self._put_in(player, paid)
        return BlindPosted(seat, paid, kind, player.all_in)

    def _put_in(self, player: PlayerState, amount: Cents) -> None:
        stack = self.seats[player.seat]
        stack.stack -= amount
        player.bet += amount
        player.committed += amount
        if stack.stack == 0:
            player.all_in = True

    def void_hand(self) -> None:
        """Cancel the hand in progress and give everyone back what they put in."""
        if not self.in_hand:
            return
        for seat, player in self.players.items():
            self.seats[seat].stack += player.committed
            player.committed = player.bet = 0
        self.pot = 0
        self.in_hand = False
        self.to_act = None
        self.street = Street.SHOWDOWN

    # -- legal actions ----------------------------------------------------------------------

    @property
    def total_pot(self) -> Cents:
        return self.pot + sum(p.bet for p in self.players.values())

    def legal(self) -> Legal:
        if self.to_act is None:
            raise PokerError("nobody is to act")
        player = self.players[self.to_act]
        stack = self.seats[self.to_act].stack
        to_call = min(stack, max(0, self.current_bet - player.bet))
        max_to = player.bet + stack
        reopened = player.acted_level is None or player.acted_level < self.reopen_level
        others_can_act = any(p.can_act for s, p in self.players.items() if s != self.to_act)
        can_raise = max_to > self.current_bet and reopened and others_can_act
        if self.current_bet == 0:
            min_to = min(max_to, max(self.big_blind, CHIP))
        else:
            min_to = min(max_to, self.current_bet + self.min_raise)
        return Legal(
            seat=self.to_act,
            to_call=to_call,
            can_check=to_call == 0,
            can_raise=can_raise,
            min_to=min_to,
            max_to=max_to,
            current_bet=self.current_bet,
            pot=self.total_pot,
        )

    # -- acting --------------------------------------------------------------------------

    def act(self, decision: Decision) -> list[Event]:
        if not self.in_hand or self.to_act is None:
            raise PokerError("no action expected")
        legal = self.legal()
        seat = self.to_act
        player = self.players[seat]
        move = decision.move
        events: list[Event] = []

        if move is Move.FOLD:
            if legal.can_check:
                move = Move.CHECK  # never fold when checking is free
            else:
                player.folded = True
                events.append(Acted(seat, Move.FOLD, player.bet, 0, False))
        if move is Move.CHECK:
            if not legal.can_check:
                raise PokerError("can't check facing a bet")
            events.append(Acted(seat, Move.CHECK, player.bet, 0, False))
        elif move is Move.CALL:
            if legal.to_call == 0:
                events.append(Acted(seat, Move.CHECK, player.bet, 0, False))
            else:
                self._put_in(player, legal.to_call)
                events.append(Acted(seat, Move.CALL, player.bet, legal.to_call, player.all_in))
        elif move in (Move.BET, Move.RAISE):
            if not legal.can_raise:
                raise PokerError("raising isn't allowed here")
            target = decision.amount
            if target % CHIP:
                raise PokerError("bets are made in whole dollars")
            if target > legal.max_to:
                raise PokerError("that's more than your stack")
            if target < legal.min_to:
                raise PokerError(f"minimum is {legal.min_to // CHIP}")
            added = target - player.bet
            raise_by = target - self.current_bet
            self._put_in(player, added)
            if raise_by >= self.min_raise:
                self.min_raise = raise_by
                self.reopen_level += 1
            # An all-in short raise still raises the price but doesn't reopen action.
            self.current_bet = target
            kind = Move.BET if legal.current_bet == 0 else Move.RAISE
            events.append(Acted(seat, kind, player.bet, added, player.all_in))

        player.acted_level = self.reopen_level
        return events + self._continue(self._next(seat, list(self.players)))

    # -- flow -----------------------------------------------------------------------------

    def _round_complete(self) -> bool:
        for p in self.players.values():
            if p.can_act and (p.acted_level is None or p.bet < self.current_bet):
                return False
        return True

    def _continue(self, candidate: int) -> list[Event]:
        """Find who acts next, or close the betting round and move the hand on."""
        live = [s for s, p in self.players.items() if p.live]
        if len(live) == 1:
            return self._finish_uncontested(live[0])
        if not self._round_complete():
            seat = candidate
            for _ in range(len(self.seats)):
                p = self.players.get(seat)
                if (
                    p is not None
                    and p.can_act
                    and (p.acted_level is None or p.bet < self.current_bet)
                ):
                    self.to_act = seat
                    return [ToAct(seat)]
                seat = (seat + 1) % len(self.seats)
            raise PokerError("betting round stuck")  # pragma: no cover
        return self._next_street()

    def _collect(self) -> list[Event]:
        events: list[Event] = []
        # Return any part of the top bet that nobody matched.
        bets = sorted(((p.bet, s) for s, p in self.players.items()), reverse=True)
        if len(bets) >= 2 and bets[0][0] > bets[1][0]:
            extra = bets[0][0] - bets[1][0]
            top = self.players[bets[0][1]]
            top.bet -= extra
            top.committed -= extra
            self.seats[top.seat].stack += extra
            if extra:
                top.all_in = False if self.seats[top.seat].stack > 0 else top.all_in
                events.append(UncalledReturned(top.seat, extra))
        gathered = sum(p.bet for p in self.players.values())
        if gathered:
            self.pot += gathered
            for p in self.players.values():
                p.bet = 0
            events.append(BetsCollected(self.pot))
        return events

    def _next_street(self) -> list[Event]:
        events = self._collect()
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.reopen_level += 1
        for p in self.players.values():
            p.acted_level = None
        self.to_act = None

        if self.street is Street.RIVER:
            return events + self._showdown()
        nxt = {Street.PREFLOP: Street.FLOP, Street.FLOP: Street.TURN, Street.TURN: Street.RIVER}
        self.street = nxt[self.street]
        count = 3 if self.street is Street.FLOP else 1
        self.deck.draw()  # burn
        new = [self.deck.draw() for _ in range(count)]
        self.board += new
        events.append(BoardDealt(self.street, tuple(new)))

        actors = [s for s, p in self.players.items() if p.can_act]
        if len(actors) < 2:
            # Everyone else is all-in: run the board out with no more betting.
            return events + self._next_street()
        first = self._next(self.button, list(self.players))
        return events + self._continue(first)

    def _finish_uncontested(self, winner: int) -> list[Event]:
        events = self._collect()
        self.to_act = None
        amount = self.pot
        self.seats[winner].stack += amount
        events.append(PotAwarded(0, amount, (winner,), (amount,), ""))
        return events + self._end_hand()

    def _showdown(self) -> list[Event]:
        self.street = Street.SHOWDOWN
        live = [s for s, p in self.players.items() if p.live]
        hands: dict[int, ShowdownHand] = {}
        for s in live:
            cards = self.players[s].cards
            seven = [*cards, *self.board]
            score = evaluate(seven)
            hands[s] = ShowdownHand(
                s, (cards[0], cards[1]), score, describe(score), tuple(best_five(seven))
            )
        events: list[Event] = [Showdown(tuple(hands[s] for s in self._from_button(live)))]
        committed = {s: p.committed for s, p in self.players.items()}
        for index, pot in enumerate(build_pots(committed, set(live))):
            best = max(hands[s].score for s in pot.eligible)
            winners = [s for s in self._from_button(pot.eligible) if hands[s].score == best]
            shares = self._split(pot.amount, len(winners))
            for seat, share in zip(winners, shares, strict=True):
                self.seats[seat].stack += share
            events.append(
                PotAwarded(index, pot.amount, tuple(winners), tuple(shares), describe(best))
            )
        self.pot = 0
        return events + self._end_hand()

    def _from_button(self, seats: list[int]) -> list[int]:
        """``seats`` ordered clockwise starting left of the button (odd-chip order)."""
        n = len(self.seats)
        return sorted(seats, key=lambda s: (s - self.button - 1) % n)

    @staticmethod
    def _split(amount: Cents, ways: int) -> list[Cents]:
        units, cents = divmod(amount, CHIP)
        base, odd = divmod(units, ways)
        shares = [(base + (1 if i < odd else 0)) * CHIP for i in range(ways)]
        shares[0] += cents  # sub-dollar dust (never expected) goes with the odd chip
        return shares

    def _end_hand(self) -> list[Event]:
        self.in_hand = False
        self.to_act = None
        stacks = tuple(s.stack if s is not None else 0 for s in self.seats)
        net = tuple(
            (self.seats[i].stack - self._starting[i]) if i in self._starting else 0
            for i in range(len(self.seats))
        )
        return [HandOver(stacks, net)]
