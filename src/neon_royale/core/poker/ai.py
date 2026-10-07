"""Computer opponents for the Hold'em table.

Each bot has a personality (how many hands it plays, how often it raises, bluffs and
calls down). Before the flop it rates its hand with the Chen formula. After the flop it
estimates its equity by Monte Carlo simulation against the live opponents' unknown
cards and weighs that against the pot odds.

Thinking is written as a generator that yields between batches of simulations, so the
game can spread the work over several frames instead of stalling the 60 FPS loop.
``decide`` runs it to completion for tests and simulations.
"""

from __future__ import annotations

import math
import random
from collections.abc import Generator
from dataclasses import dataclass

from ..cards import Card, Rank, full_deck
from .engine import CHIP, Decision, Legal, Move, PokerTable, Street
from .evaluator import evaluate


@dataclass(frozen=True)
class Personality:
    title: str
    looseness: float  # 0..1: share of starting hands played
    aggression: float  # 0..1: raise rather than call
    bluff: float  # chance of betting or raising with nothing
    stickiness: float  # 0..1: willingness to call down light
    sizing: float  # typical bet as a fraction of the pot


PERSONALITIES: dict[str, Personality] = {
    "rock": Personality("Rock", 0.15, 0.35, 0.02, 0.15, 0.55),
    "shark": Personality("Shark", 0.35, 0.75, 0.10, 0.35, 0.7),
    "maniac": Personality("Maniac", 0.75, 0.9, 0.28, 0.45, 0.95),
    "station": Personality("Calling station", 0.6, 0.15, 0.03, 0.95, 0.5),
    "solid": Personality("Solid", 0.4, 0.5, 0.07, 0.45, 0.65),
}

# Made-up characters who rotate through the empty seats.
ROSTER: tuple[tuple[str, str, tuple[int, int, int]], ...] = (
    ("Neon Nina", "maniac", (255, 70, 160)),
    ("Dusty Dalton", "rock", (210, 170, 110)),
    ("The Professor", "shark", (110, 200, 255)),
    ("Cherry Bloom", "station", (255, 120, 120)),
    ("Viktor Vance", "shark", (170, 120, 255)),
    ("Lucky Lin", "solid", (120, 255, 160)),
    ("Big Sal", "station", (255, 190, 80)),
    ("Jade Moreau", "solid", (80, 230, 200)),
    ("Rex Rollins", "maniac", (255, 140, 60)),
    ("Old Gus", "rock", (190, 190, 210)),
)

SIMULATIONS = 360
BATCH = 40


def chen_score(cards: list[Card]) -> float:
    """Bill Chen's quick pre-flop hand rating (about -1 to 20)."""
    a, b = sorted(cards, key=lambda c: int(c.rank), reverse=True)
    high = a.rank

    def points(rank: Rank) -> float:
        return {Rank.ACE: 10, Rank.KING: 8, Rank.QUEEN: 7, Rank.JACK: 6}.get(rank, int(rank) / 2)

    if a.rank == b.rank:
        return max(5.0, points(high) * 2)
    score = points(high)
    if a.suit == b.suit:
        score += 2
    gap = int(a.rank) - int(b.rank) - 1
    score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and int(a.rank) < int(Rank.QUEEN):
        score += 1
    return math.ceil(score)


def equity_job(
    hole: list[Card],
    board: list[Card],
    opponents: int,
    rng: random.Random,
    simulations: int = SIMULATIONS,
    batch: int = BATCH,
) -> Generator[None, None, float]:
    """Monte Carlo share of the pot won against ``opponents`` random hands."""
    if opponents <= 0:
        return 1.0
    known = set(hole) | set(board)
    deck = [c for c in full_deck() if c not in known]
    need_board = 5 - len(board)
    draw = need_board + 2 * opponents
    total = 0.0
    for i in range(simulations):
        sample = rng.sample(deck, draw)
        full_board = board + sample[:need_board]
        mine = evaluate(hole + full_board)
        best_other = 0
        ties = 0
        for k in range(opponents):
            start = need_board + 2 * k
            theirs = evaluate(sample[start : start + 2] + full_board)
            if theirs > best_other:
                best_other = theirs
        if mine > best_other:
            total += 1.0
        elif mine == best_other:
            # Count how many opponents share the best hand to split fairly.
            ties = sum(
                evaluate(sample[need_board + 2 * k : need_board + 2 * k + 2] + full_board) == mine
                for k in range(opponents)
            )
            total += 1.0 / (ties + 1)
        if (i + 1) % batch == 0:
            yield
    return total / simulations


def _round_chips(amount: float) -> int:
    return max(CHIP, round(amount / CHIP) * CHIP)


def _raise_to(legal: Legal, target: float) -> Decision:
    amount = min(legal.max_to, max(legal.min_to, _round_chips(target)))
    return Decision(legal.raise_move, amount)


def think(table: PokerTable, seat: int, rng: random.Random) -> Generator[None, None, Decision]:
    """Decide the bot's action; yields periodically while simulating."""
    legal = table.legal()
    profile = PERSONALITIES.get(table.seats[seat].profile, PERSONALITIES["solid"])
    me = table.players[seat]
    bb = table.big_blind
    stack = table.seats[seat].stack
    opponents = sum(1 for s, p in table.players.items() if s != seat and p.live)

    if table.street is Street.PREFLOP:
        return _preflop(legal, profile, me.cards, bb, stack, rng)

    equity = yield from equity_job(me.cards, table.board, opponents, rng)
    return _postflop(legal, profile, equity, opponents, stack, rng)


def decide(table: PokerTable, seat: int, rng: random.Random) -> Decision:
    job = think(table, seat, rng)
    while True:
        try:
            next(job)
        except StopIteration as done:
            return done.value


def _preflop(
    legal: Legal,
    p: Personality,
    hole: list[Card],
    bb: int,
    stack: int,
    rng: random.Random,
) -> Decision:
    strength = chen_score(hole) + rng.uniform(-1.0, 1.0)
    play_at = 10 - 6 * p.looseness
    raise_at = 12 - 4 * p.aggression
    facing = legal.current_bet
    pressure = facing / bb

    if stack <= 12 * bb and strength >= play_at + 1 and legal.can_raise:
        return Decision(legal.raise_move, legal.max_to)  # short stack: shove or fold
    if facing <= bb:  # unopened, limped, or the big blind's option
        if strength >= raise_at and legal.can_raise:
            return _raise_to(legal, bb * rng.choice((2.5, 3, 3, 3.5)) + legal.pot * 0.1)
        if legal.can_check:
            return Decision(Move.CHECK)
        if strength >= play_at:
            return Decision(Move.CALL)
        return Decision(Move.FOLD)
    # Facing a raise.
    if strength >= raise_at + 3 and legal.can_raise and rng.random() < 0.4 + p.aggression * 0.5:
        return _raise_to(legal, facing * 3)
    if strength >= play_at + min(5.0, pressure / 2.5) - p.stickiness:
        return Decision(Move.CALL)
    return Decision(Move.FOLD)


def _postflop(
    legal: Legal,
    p: Personality,
    equity: float,
    opponents: int,
    stack: int,
    rng: random.Random,
) -> Decision:
    pot = max(legal.pot, CHIP)
    call = legal.to_call
    roll = rng.random()
    value_at = 0.72 - 0.15 * p.aggression + 0.04 * (opponents - 1)
    size = pot * (p.sizing + rng.uniform(-0.15, 0.15))

    if call == 0:
        if equity >= value_at and legal.can_raise:
            if equity > 0.9 and roll < 0.25 * (1 - p.aggression):
                return Decision(Move.CHECK)  # slow-play the monster
            return _raise_to(legal, size)
        if roll < p.bluff * (1.6 if opponents == 1 else 0.8) and legal.can_raise:
            return _raise_to(legal, size * 0.8)
        return Decision(Move.CHECK)

    pot_odds = call / (pot + call)
    if equity >= value_at + 0.08 and legal.can_raise and roll < 0.3 + 0.6 * p.aggression:
        target = legal.current_bet + pot * (0.7 + 0.5 * p.aggression)
        if stack < pot or equity > 0.93:
            target = legal.max_to
        return _raise_to(legal, target)
    if equity + 0.12 * p.stickiness >= pot_odds + 0.03:
        return Decision(Move.CALL)
    if legal.can_raise and roll < p.bluff * 0.35 and opponents == 1:
        return _raise_to(legal, legal.current_bet * 2.5)
    return Decision(Move.FOLD)
