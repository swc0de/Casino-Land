"""Blackjack: a six-deck shoe game with Las Vegas Strip rules.

Rules:

* 6 decks, reshuffled when the cut card (about 75% in) comes out.
* Dealer stands on all 17s (S17) and peeks for blackjack when showing an ace or a
  ten-value card, so a player never loses doubles or splits to a dealer natural.
* Blackjack pays 3:2. Insurance (up to half the bet) pays 2:1 when the dealer shows an ace.
* Double down on any first two cards, including after a split.
* Split any two cards of equal value, up to four hands. Split aces get one card each,
  can't be re-split, and 21 on a split hand is not a blackjack.
* Late surrender on the first two cards of the original hand.

The table is a state machine. Every action returns a list of events describing what
happened in order (cards dealt, the hole card turned, hands settled); the screen
animates those events and never decides outcomes itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from .cards import Card, Rank, Shoe
from .money import Cents, dollars
from .wallet import InsufficientFundsError, Wallet

DECKS = 6
PENETRATION = 0.75
MIN_BET: Cents = dollars(5)
MAX_BET: Cents = dollars(5_000)
MAX_HANDS = 4


def card_value(card: Card) -> int:
    if card.rank is Rank.ACE:
        return 11
    return min(10, int(card.rank))


def hand_value(cards: list[Card]) -> tuple[int, bool]:
    """Best total and whether it is soft (an ace still counting as 11)."""
    total = sum(card_value(c) for c in cards)
    aces = sum(c.rank is Rank.ACE for c in cards)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


class Phase(Enum):
    BETTING = auto()
    INSURANCE = auto()
    PLAYER = auto()
    SETTLED = auto()


class Action(Enum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"


class Outcome(Enum):
    BLACKJACK = "Blackjack"
    WIN = "Win"
    PUSH = "Push"
    LOSE = "Lose"
    BUST = "Bust"
    SURRENDER = "Surrender"


@dataclass
class Hand:
    cards: list[Card] = field(default_factory=list)
    bet: Cents = 0
    doubled: bool = False
    from_split: bool = False
    split_aces: bool = False
    stood: bool = False
    surrendered: bool = False

    @property
    def total(self) -> int:
        return hand_value(self.cards)[0]

    @property
    def soft(self) -> bool:
        return hand_value(self.cards)[1]

    @property
    def busted(self) -> bool:
        return self.total > 21

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.total == 21 and not self.from_split

    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and card_value(self.cards[0]) == card_value(self.cards[1])

    @property
    def done(self) -> bool:
        return (
            self.stood
            or self.surrendered
            or self.busted
            or self.total == 21
            or self.doubled
            or (self.split_aces and len(self.cards) >= 2)
        )

    def describe(self) -> str:
        if self.is_blackjack:
            return "Blackjack"
        if self.busted:
            return f"Bust ({self.total})"
        total, soft = hand_value(self.cards)
        return f"Soft {total}" if soft and total < 21 else str(total)


# -- events ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Shuffled:
    pass


@dataclass(frozen=True)
class CardDealt:
    to: str  # "player" or "dealer"
    hand: int
    card: Card
    face_up: bool = True


@dataclass(frozen=True)
class HoleRevealed:
    card: Card


@dataclass(frozen=True)
class InsuranceOffered:
    max_amount: Cents


@dataclass(frozen=True)
class Peeked:
    """The dealer checked the hole card for blackjack."""

    blackjack: bool


@dataclass(frozen=True)
class InsuranceSettled:
    stake: Cents
    returned: Cents


@dataclass(frozen=True)
class Split:
    hand: int  # the hand that was split
    new_hand: int  # index of the hand that took the second card


@dataclass(frozen=True)
class Doubled:
    hand: int
    bet: Cents


@dataclass(frozen=True)
class Surrendered:
    hand: int


@dataclass(frozen=True)
class TurnChanged:
    hand: int


@dataclass(frozen=True)
class HandSettled:
    hand: int
    outcome: Outcome
    stake: Cents
    returned: Cents


@dataclass(frozen=True)
class RoundOver:
    wagered: Cents
    returned: Cents

    @property
    def net(self) -> Cents:
        return self.returned - self.wagered


Event = (
    Shuffled
    | CardDealt
    | HoleRevealed
    | InsuranceOffered
    | Peeked
    | InsuranceSettled
    | Split
    | Doubled
    | Surrendered
    | TurnChanged
    | HandSettled
    | RoundOver
)


class RuleError(Exception):
    """An action the rules don't allow right now."""


# -- the table ------------------------------------------------------------------------


class BlackjackTable:
    def __init__(
        self,
        wallet: Wallet,
        rng: random.Random | None = None,
        shoe: Shoe | None = None,
        min_bet: Cents = MIN_BET,
        max_bet: Cents = MAX_BET,
    ) -> None:
        self.wallet = wallet
        self.shoe = shoe or Shoe(DECKS, rng or random.Random(), PENETRATION)
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.phase = Phase.BETTING
        self.hands: list[Hand] = []
        self.dealer: list[Card] = []
        self.hole_hidden = False
        self.active = 0
        self.insurance: Cents = 0
        self.last_bet: Cents = 0
        self._wagered: Cents = 0
        self._returned: Cents = 0
        self._acted = False

    # -- helpers ------------------------------------------------------------------------

    @property
    def hand(self) -> Hand:
        return self.hands[self.active]

    @property
    def upcard(self) -> Card | None:
        return self.dealer[0] if self.dealer else None

    @property
    def dealer_total(self) -> int:
        cards = self.dealer[:1] if self.hole_hidden else self.dealer
        return hand_value(cards)[0]

    def _debit(self, amount: Cents) -> None:
        try:
            self.wallet.debit(amount)
        except InsufficientFundsError as exc:
            raise RuleError("not enough chips") from exc
        self._wagered += amount

    def _draw_player(self, index: int, events: list[Event]) -> None:
        card = self.shoe.draw()
        self.hands[index].cards.append(card)
        events.append(CardDealt("player", index, card))

    def _draw_dealer(self, events: list[Event], face_up: bool = True) -> None:
        card = self.shoe.draw()
        self.dealer.append(card)
        events.append(CardDealt("dealer", 0, card, face_up))

    def _require(self, phase: Phase) -> None:
        if self.phase is not phase:
            raise RuleError(f"can't do that during {self.phase.name.lower()}")

    # -- betting and the deal -----------------------------------------------------------

    def deal(self, bet: Cents) -> list[Event]:
        self._require(Phase.BETTING)
        if bet < self.min_bet or bet > self.max_bet:
            raise RuleError("bet is outside the table limits")
        if bet % 100:
            raise RuleError("bets are in whole dollars")
        events: list[Event] = []
        self._wagered = self._returned = 0
        self._debit(bet)
        self.last_bet = bet
        if self.shoe.needs_shuffle:
            self.shoe.shuffle()
            events.append(Shuffled())
        self.hands = [Hand(bet=bet)]
        self.dealer = []
        self.active = 0
        self.insurance = 0
        self._acted = False
        self.hole_hidden = True

        self._draw_player(0, events)
        self._draw_dealer(events)
        self._draw_player(0, events)
        self._draw_dealer(events, face_up=False)

        up = self.dealer[0]
        if up.rank is Rank.ACE:
            self.phase = Phase.INSURANCE
            events.append(InsuranceOffered(bet // 2))
            return events
        if card_value(up) == 10:
            events += self._peek()
            if self.phase is Phase.SETTLED:
                return events
        return events + self._start_player_turn()

    def take_insurance(self, amount: Cents | None = None) -> list[Event]:
        """Insure against a dealer blackjack (default: the maximum, half the bet)."""
        self._require(Phase.INSURANCE)
        limit = self.hands[0].bet // 2
        amount = limit if amount is None else amount
        if not 0 < amount <= limit:
            raise RuleError("insurance is up to half your bet")
        self._debit(amount)
        self.insurance = amount
        return self._after_insurance()

    def decline_insurance(self) -> list[Event]:
        self._require(Phase.INSURANCE)
        return self._after_insurance()

    def _after_insurance(self) -> list[Event]:
        insured: InsuranceSettled | None = None
        if self.insurance:
            # Resolve the side bet first so the round totals include it.
            dealer_bj = hand_value(self.dealer)[0] == 21
            returned = self.insurance * 3 if dealer_bj else 0
            self._returned += returned
            self.wallet.credit(returned)
            insured = InsuranceSettled(self.insurance, returned)
        events = self._peek()
        if insured is not None:
            settle_at = next(
                (i for i, e in enumerate(events) if isinstance(e, HandSettled)), len(events)
            )
            events.insert(settle_at, insured)
        if self.phase is Phase.SETTLED:
            return events
        return events + self._start_player_turn()

    def _peek(self) -> list[Event]:
        dealer_bj = hand_value(self.dealer)[0] == 21
        events: list[Event] = [Peeked(dealer_bj)]
        if dealer_bj:
            self.hole_hidden = False
            events.append(HoleRevealed(self.dealer[1]))
            events += self._settle()
        return events

    def _start_player_turn(self) -> list[Event]:
        if self.hands[0].is_blackjack:
            self.hole_hidden = False
            return [HoleRevealed(self.dealer[1]), *self._settle()]
        self.phase = Phase.PLAYER
        return [TurnChanged(0)]

    # -- player decisions ---------------------------------------------------------------

    def legal_actions(self) -> set[Action]:
        if self.phase is not Phase.PLAYER:
            return set()
        hand = self.hand
        actions = {Action.HIT, Action.STAND}
        two_cards = len(hand.cards) == 2
        if two_cards and self.wallet.can_afford(hand.bet):
            actions.add(Action.DOUBLE)
            if hand.is_pair and len(self.hands) < MAX_HANDS and not hand.split_aces:
                actions.add(Action.SPLIT)
        if two_cards and len(self.hands) == 1 and not self._acted:
            actions.add(Action.SURRENDER)
        return actions

    def act(self, action: Action) -> list[Event]:
        if action not in self.legal_actions():
            raise RuleError(f"can't {action.value} now")
        self._acted = True
        events: list[Event] = []
        hand = self.hand
        if action is Action.HIT:
            self._draw_player(self.active, events)
        elif action is Action.STAND:
            hand.stood = True
        elif action is Action.DOUBLE:
            self._debit(hand.bet)
            hand.bet *= 2
            hand.doubled = True
            events.append(Doubled(self.active, hand.bet))
            self._draw_player(self.active, events)
        elif action is Action.SPLIT:
            events += self._split()
        elif action is Action.SURRENDER:
            hand.surrendered = True
            events.append(Surrendered(self.active))
        return events + self._advance()

    def hit(self) -> list[Event]:
        return self.act(Action.HIT)

    def stand(self) -> list[Event]:
        return self.act(Action.STAND)

    def double(self) -> list[Event]:
        return self.act(Action.DOUBLE)

    def split(self) -> list[Event]:
        return self.act(Action.SPLIT)

    def surrender(self) -> list[Event]:
        return self.act(Action.SURRENDER)

    def _split(self) -> list[Event]:
        hand = self.hand
        self._debit(hand.bet)
        aces = hand.cards[0].rank is Rank.ACE
        new = Hand(cards=[hand.cards.pop()], bet=hand.bet, from_split=True, split_aces=aces)
        hand.from_split = True
        hand.split_aces = aces
        new_index = self.active + 1
        self.hands.insert(new_index, new)
        events: list[Event] = [Split(self.active, new_index)]
        self._draw_player(self.active, events)
        if aces:
            self._draw_player(new_index, events)
        return events

    def _advance(self) -> list[Event]:
        """Move to the next hand that still needs decisions, or let the dealer play."""
        events: list[Event] = []
        while self.active < len(self.hands):
            hand = self.hand
            if len(hand.cards) == 1:  # second hand of a split gets its card now
                self._draw_player(self.active, events)
            if not hand.done:
                return events
            if self.active + 1 < len(self.hands):
                self.active += 1
                events.append(TurnChanged(self.active))
            else:
                break
        return events + self._dealer_turn()

    # -- dealer and settlement ----------------------------------------------------------

    def _dealer_turn(self) -> list[Event]:
        events: list[Event] = [HoleRevealed(self.dealer[1])]
        self.hole_hidden = False
        live = any(not h.busted and not h.surrendered for h in self.hands)
        if live:
            while hand_value(self.dealer)[0] < 17:
                self._draw_dealer(events)
        return events + self._settle()

    def _settle(self) -> list[Event]:
        events: list[Event] = []
        dealer_total, _ = hand_value(self.dealer)
        dealer_bj = len(self.dealer) == 2 and dealer_total == 21
        for i, hand in enumerate(self.hands):
            outcome, returned = self._outcome(hand, dealer_total, dealer_bj)
            self._returned += returned
            self.wallet.credit(returned)
            events.append(HandSettled(i, outcome, hand.bet, returned))
        events.append(RoundOver(self._wagered, self._returned))
        self.phase = Phase.SETTLED
        return events

    @staticmethod
    def _outcome(hand: Hand, dealer_total: int, dealer_bj: bool) -> tuple[Outcome, Cents]:
        bet = hand.bet
        if hand.surrendered:
            return Outcome.SURRENDER, bet // 2
        if hand.busted:
            return Outcome.BUST, 0
        if hand.is_blackjack:
            if dealer_bj:
                return Outcome.PUSH, bet
            return Outcome.BLACKJACK, bet + bet * 3 // 2
        if dealer_bj:
            return Outcome.LOSE, 0
        if dealer_total > 21 or hand.total > dealer_total:
            return Outcome.WIN, bet * 2
        if hand.total == dealer_total:
            return Outcome.PUSH, bet
        return Outcome.LOSE, 0

    def new_round(self) -> None:
        """Clear the table after a settled round so the next bet can be placed."""
        self._require(Phase.SETTLED)
        self.phase = Phase.BETTING
        self.hands = []
        self.dealer = []
        self.hole_hidden = False
        self.active = 0
        self.insurance = 0


# -- basic strategy -------------------------------------------------------------------

# Columns: dealer upcard 2..10, then ace (11).
# H hit, S stand, D double (else hit), Ds double (else stand), P split,
# Rh surrender (else hit). Six decks, S17, double after split, late surrender.
_HARD = {
    17: "S S S S S S S S S S",
    16: "S S S S S H H Rh Rh Rh",
    15: "S S S S S H H H Rh H",
    14: "S S S S S H H H H H",
    13: "S S S S S H H H H H",
    12: "H H S S S H H H H H",
    11: "D D D D D D D D D H",
    10: "D D D D D D D D H H",
    9: "H D D D D H H H H H",
    8: "H H H H H H H H H H",
}
_SOFT = {
    20: "S S S S S S S S S S",
    19: "S S S S S S S S S S",
    18: "S Ds Ds Ds Ds S S H H H",
    17: "H D D D D H H H H H",
    16: "H H D D D H H H H H",
    15: "H H D D D H H H H H",
    14: "H H H D D H H H H H",
    13: "H H H D D H H H H H",
}
_PAIRS = {  # by card value; "N" means don't split (play the total)
    11: "P P P P P P P P P P",
    10: "N N N N N N N N N N",
    9: "P P P P P S P P S S",
    8: "P P P P P P P P P P",
    7: "P P P P P P H H H H",
    6: "P P P P P H H H H H",
    5: "N N N N N N N N N N",
    4: "H H H P P H H H H H",
    3: "P P P P P P H H H H",
    2: "P P P P P P H H H H",
}


def _lookup(table: dict[int, str], key: int, upcard: Card) -> str:
    column = card_value(upcard) - 2  # 2..11 -> 0..9
    return table[key].split()[column]


def basic_strategy(hand: Hand, upcard: Card, legal: set[Action]) -> Action:
    """The mathematically best play for this game's rules (no card counting)."""
    if Action.SPLIT in legal and hand.is_pair:
        code = _lookup(_PAIRS, card_value(hand.cards[0]), upcard)
        if code == "P":
            return Action.SPLIT
    total, soft = hand_value(hand.cards)
    if soft and total == 12:  # a pair of aces that can't be split again
        code = "H"
    elif soft and 13 <= total < 21:
        code = _lookup(_SOFT, total, upcard)
    elif total >= 17:
        code = "S"
    elif total <= 8:
        code = "H"
    else:
        code = _lookup(_HARD, total, upcard)
    if code in ("D", "Ds"):
        if Action.DOUBLE in legal:
            return Action.DOUBLE
        return Action.STAND if code == "Ds" else Action.HIT
    if code == "Rh":
        return Action.SURRENDER if Action.SURRENDER in legal else Action.HIT
    if code == "S" or total >= 21:
        return Action.STAND
    return Action.HIT
