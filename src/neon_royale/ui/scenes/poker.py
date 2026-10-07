"""Texas Hold'em table: you against five computer players."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field

import pygame

from ...core.money import Cents, fmt
from ...core.poker import ai
from ...core.poker import engine as pk
from ...core.poker.engine import CHIP, Decision, Legal, Move
from ...core.poker.room import BIG_BLIND, HUMAN_SEAT, MIN_BUY_IN, PokerRoom, RoomError
from .. import fonts, theme
from ..caches import optimise
from ..fx.glow import NeonGraphic, neon_text
from ..fx.marquee import Marquee
from ..fx.tween import ease_in_out_cubic, ease_out_back, ease_out_cubic
from ..render.backdrop import felt, night_sky
from ..render.chips import draw_amount
from ..sprites import CardSprite
from ..stage import Stage
from ..theme import Color, lerp_color
from ..widgets import CountingLabel, Slider, draw_panel

TABLE_CENTER = (640, 312)
TABLE_RX, TABLE_RY = 478, 212
DECK_POS = (640, 200)
POT_POS = (640, 222)
BOARD_Y = 306
BOARD_W = 70
BOT_CARD_W = 50
HUMAN_CARD_W = 84
CHIP_D = 28
THINK_BUDGET = 0.003  # seconds of bot simulation per frame
# Where everything sits for each seat (seat 0 is you, the rest run clockwise).
LAYOUT: dict[int, dict[str, tuple[float, float]]] = {
    0: {
        "avatar": (640, 640),
        "cards": (640, 520),
        "bet": (640, 446),
        "button": (742, 498),
        "label": (490, 594),
    },
    1: {
        "avatar": (226, 470),
        "cards": (346, 452),
        "bet": (432, 410),
        "button": (318, 392),
        "label": (226, 400),
    },
    2: {
        "avatar": (164, 196),
        "cards": (296, 226),
        "bet": (380, 268),
        "button": (282, 296),
        "label": (164, 126),
    },
    3: {
        "avatar": (640, 62),
        "cards": (538, 150),
        "bet": (752, 178),
        "button": (842, 128),
        "label": (790, 62),
    },
    4: {
        "avatar": (1116, 196),
        "cards": (984, 226),
        "bet": (900, 268),
        "button": (998, 296),
        "label": (1116, 126),
    },
    5: {
        "avatar": (1054, 470),
        "cards": (934, 452),
        "bet": (848, 410),
        "button": (962, 392),
        "label": (1054, 400),
    },
}
SEAT_POS = {seat: spots["avatar"] for seat, spots in LAYOUT.items()}
ACTION_COLORS: dict[str, Color] = {
    "FOLD": theme.TEXT_MUTED,
    "CHECK": theme.CYAN,
    "CALL": theme.LIME,
    "BET": theme.GOLD,
    "RAISE": theme.ORANGE,
    "ALL IN": theme.PINK,
    "SB": theme.TEXT_DIM,
    "BB": theme.TEXT_DIM,
}


def _snake(name: str) -> str:
    """``HoleCards`` -> ``hole_cards``: event class names map to ``_on_*`` handlers."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


@dataclass
class Chips:
    amount: Cents
    pos: tuple[float, float]
    alpha: float = 1.0


@dataclass
class SeatView:
    index: int
    name: str = ""
    profile: str = ""
    color: Color = (200, 200, 200)
    stack: Cents = 0
    bet: Cents = 0
    present: bool = False
    in_hand: bool = False
    folded: bool = False
    all_in: bool = False
    cards: list[CardSprite] = field(default_factory=list)
    label: str = ""
    label_age: float = 0.0
    hand_desc: str = ""
    winner: float = 0.0
    fade: float = 1.0

    @property
    def avatar(self) -> tuple[float, float]:
        return SEAT_POS[self.index]

    @property
    def human(self) -> bool:
        return self.index == HUMAN_SEAT

    def card_pos(self, i: int) -> tuple[float, float]:
        x, y = LAYOUT[self.index]["cards"]
        spread = 60 if self.human else 28
        return x + (i - 0.5) * spread, y

    @property
    def bet_pos(self) -> tuple[float, float]:
        return LAYOUT[self.index]["bet"]

    @property
    def button_pos(self) -> tuple[float, float]:
        return LAYOUT[self.index]["button"]

    @property
    def label_pos(self) -> tuple[float, float]:
        return LAYOUT[self.index]["label"]


def render_table() -> pygame.Surface:
    surf = night_sky()
    shade = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    shade.fill((0, 0, 0, 90))
    surf.blit(shade, (0, 0))
    cx, cy = TABLE_CENTER
    outer = pygame.Rect(0, 0, (TABLE_RX + 34) * 2, (TABLE_RY + 34) * 2)
    outer.center = (cx, cy)
    inner = pygame.Rect(0, 0, TABLE_RX * 2, TABLE_RY * 2)
    inner.center = (cx, cy)
    # Shadow, padded rail and felt.
    shadow = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 150), outer.move(0, 18))
    for _ in range(3):
        shadow = pygame.transform.box_blur(shadow, 10)
    surf.blit(shadow, (0, 0))
    pygame.draw.ellipse(surf, (44, 20, 12), outer)
    pygame.draw.ellipse(surf, (90, 46, 22), outer.inflate(-10, -10))
    pygame.draw.ellipse(surf, (60, 28, 14), outer.inflate(-30, -30))
    cloth = felt(inner.size, theme.FELT_RED, theme.FELT_RED_DARK, seed=31)
    mask = pygame.Surface(inner.size, pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255, 255), mask.get_rect())
    cloth = cloth.convert_alpha() if pygame.display.get_surface() else cloth.copy()
    clipped = pygame.Surface(inner.size, pygame.SRCALPHA)
    clipped.blit(cloth, (0, 0))
    clipped.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(clipped, inner)
    # Neon rim and a printed betting line.
    rim = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    pygame.draw.ellipse(rim, (255, 255, 255), inner.inflate(6, 6), 4)
    glow = NeonGraphic(rim, theme.PINK, 12)
    surf.blit(glow.halo, (-glow.margin, -glow.margin))
    surf.blit(glow.core, (-glow.margin, -glow.margin))
    pygame.draw.ellipse(surf, (210, 120, 140), inner.inflate(-190, -150), 2)
    logo = fonts.get("marquee", 40).render("NEON ROYALE", True, (150, 40, 70))
    surf.blit(logo, logo.get_rect(center=(cx, cy + 112)))
    hint = fonts.get("body_bold", 16).render(
        "NO-LIMIT TEXAS HOLD'EM  ·  BLINDS $5/$10", True, (190, 110, 130)
    )
    surf.blit(hint, hint.get_rect(center=(cx, cy + 150)))
    return optimise(surf)


class PokerScene(Stage):
    help_topic = "poker"
    ambience = 0.4

    def shutdown(self) -> None:
        self.room.abandon()

    def enter(self) -> None:
        app = self.app
        self.room = PokerRoom(app.casino.wallet, app.rng)
        self.table = self.room.table
        self.background = render_table()
        self.marquee = Marquee(
            pygame.Rect(10, 10, theme.WIDTH - 20, theme.HEIGHT - 20),
            spacing=34,
            radius=4,
            pattern="wave",
            speed=3,
            rng=app.rng,
        )
        self.seats = [SeatView(i) for i in range(len(self.table.seats))]
        self.board: list[CardSprite] = []
        self.pot: Cents = 0
        self.pot_chips: list[Chips] = []
        self.flying: list[Chips] = []
        self.button_pos: tuple[float, float] = SEAT_POS[0]
        self.active_seat: int | None = None
        self.think_started = 0.0
        self.street_label = ""
        self.mode = "buyin"  # buyin | waiting | human | bot | between
        self.decision: Decision | None = None
        self.leaving = False
        self.skip_pause = False
        self.hand_wagered: Cents = 0
        self._showdown_best: dict[int, tuple] = {}
        self._pending_holes: list[pk.HoleCards] = []
        self.balance = CountingLabel((44, 678), app.casino.balance, "Bankroll", "midleft", 26)
        self._sync_seats(animate=False)

        # Buy-in dialog.
        self.buyin_amount = 0
        self.buyin_slider = Slider((440, 380, 400, 24), 0.5, self._buyin_changed, theme.GOLD)
        self.btn_sit = self.button(
            (470, 440, 160, 54), "SIT DOWN", self.sit_down, color=theme.GOLD, hotkey=pygame.K_RETURN
        )
        self.btn_leave_dialog = self.button(
            (650, 440, 160, 54), "LOBBY", self.leave, color=theme.PINK
        )
        # Decisions.
        y = 652
        self.btn_fold = self.button(
            (878, y, 116, 52),
            "FOLD",
            lambda: self.choose("fold"),
            color=theme.TEXT_DIM,
            hotkey=pygame.K_f,
            font_size=20,
        )
        self.btn_call = self.button(
            (1002, y, 126, 52),
            "CHECK",
            lambda: self.choose("call"),
            color=theme.LIME,
            hotkey=pygame.K_c,
            font_size=18,
        )
        self.btn_raise = self.button(
            (1136, y, 126, 52),
            "RAISE",
            lambda: self.choose("raise"),
            color=theme.GOLD,
            hotkey=pygame.K_r,
            font_size=18,
        )
        self.raise_slider = Slider((884, 610, 220, 22), 0.0, self._raise_changed, theme.GOLD)
        self.quick = [
            self.button(
                (1116, 566 + 0, 66, 34),
                "½",
                lambda: self.quick_bet(0.5),
                color=theme.ORANGE,
                font_size=16,
            ),
            self.button(
                (1188, 566, 74, 34),
                "POT",
                lambda: self.quick_bet(1.0),
                color=theme.ORANGE,
                font_size=16,
            ),
        ]
        self.btn_allin = self.button(
            (1116, 604, 146, 34),
            "ALL IN",
            lambda: self.quick_bet(-1),
            color=theme.PINK,
            font_size=16,
        )
        self.raise_to: Cents = 0
        # Table controls.
        self.button((24, 24, 130, 44), "LOBBY", self.leave, color=theme.PINK, font_size=18)
        self.add_help_button()
        self.btn_topup = self.button(
            (24, 76, 130, 40), "ADD CHIPS", self.top_up, color=theme.CYAN, font_size=16
        )
        self._prepare_buyin()
        self._sync_buttons()

    # -- seats ----------------------------------------------------------------------------

    def _sync_seats(self, animate: bool = True) -> None:
        """Copy names and stacks from the table between hands (new bots fade in)."""
        for view in self.seats:
            seat = self.table.seats[view.index]
            if seat is None:
                view.present = False
                continue
            if animate and (not view.present or view.name != seat.name):
                view.fade = 0.0
                self.anim.to(view, "fade", 1.0, 0.6)
            view.present = True
            view.name = seat.name
            view.profile = ai.PERSONALITIES[seat.profile].title if not seat.is_human else ""
            view.color = seat.color
            view.stack = seat.stack

    # -- buying in --------------------------------------------------------------------------

    def _prepare_buyin(self) -> None:
        self.mode = "buyin"
        low = MIN_BUY_IN
        high = min(self.room.wallet.balance, 200 * BIG_BLIND)
        self.buyin_range = (low, high)
        self.buyin_slider.value = 0.5
        self._buyin_changed(0.5)

    def _buyin_changed(self, value: float) -> None:
        low, high = self.buyin_range if hasattr(self, "buyin_range") else (MIN_BUY_IN, MIN_BUY_IN)
        if high < low:
            self.buyin_amount = 0
            return
        amount = low + (high - low) * value
        self.buyin_amount = int(round(amount / (10 * CHIP)) * 10 * CHIP)
        self.buyin_amount = max(low, min(high - high % CHIP, self.buyin_amount))

    def sit_down(self) -> None:
        if self.mode != "buyin":
            return
        try:
            self.room.sit_down(self.buyin_amount)
        except RoomError as exc:
            self._refuse(str(exc).capitalize())
            return
        self.sound.play("chip_stack")
        self.balance.set(self.app.casino.balance)
        self._sync_seats()
        self.mode = "between"
        self.director.run(self._session())

    def top_up(self) -> None:
        if self.mode not in ("between",) or self.table.in_hand:
            self._refuse("Add chips between hands")
            return
        low, high = self.room.buy_in_range()
        amount = min(high, max(low, 50 * BIG_BLIND))
        try:
            self.room.top_up(amount - amount % CHIP)
        except RoomError as exc:
            self._refuse(str(exc).capitalize())
            return
        self.sound.play("chip_stack")
        self.seats[HUMAN_SEAT].stack = self.room.stack
        self.balance.set(self.app.casino.balance)
        self.toast.show(f"Added {fmt(amount)} to your stack", theme.CYAN)

    def leave(self) -> None:
        if self.table.in_hand and self.room.seated:
            self.leaving = True
            human = self.table.players.get(HUMAN_SEAT)
            if self.mode == "human":
                self.choose("fold")
            elif human is not None and not human.folded:
                self.toast.show("You'll leave when this hand ends", theme.GOLD)
            return
        self._cash_out_and_go()

    def _cash_out_and_go(self) -> None:
        amount = self.room.cash_out()
        if amount:
            self.toast.show(f"Cashed out {fmt(amount)}", theme.GOLD)
        self.app.save()
        self.app.go("lobby")

    def _refuse(self, message: str) -> None:
        self.sound.play("ui_error", 0.7)
        self.toast.show(message, theme.LOSE)

    # -- the player's decision -------------------------------------------------------------

    def _legal(self) -> Legal | None:
        if self.mode != "human" or self.table.to_act != HUMAN_SEAT:
            return None
        return self.table.legal()

    def _raise_changed(self, value: float) -> None:
        legal = self._legal()
        if legal is None:
            return
        span = legal.max_to - legal.min_to
        amount = legal.min_to + span * value**2  # finer control at the low end
        self.raise_to = int(min(legal.max_to, max(legal.min_to, round(amount / CHIP) * CHIP)))
        self._sync_buttons()

    def _set_raise(self, amount: Cents) -> None:
        legal = self._legal()
        if legal is None:
            return
        self.raise_to = int(min(legal.max_to, max(legal.min_to, round(amount / CHIP) * CHIP)))
        span = legal.max_to - legal.min_to
        self.raise_slider.value = math.sqrt((self.raise_to - legal.min_to) / span) if span else 1.0
        self._sync_buttons()

    def quick_bet(self, fraction: float) -> None:
        legal = self._legal()
        if legal is None:
            return
        if fraction < 0:
            self._set_raise(legal.max_to)
        else:
            after_call = legal.pot + legal.to_call
            self._set_raise(legal.current_bet + after_call * fraction)
        self.sound.play("chip_clack", 0.5)

    def choose(self, kind: str) -> None:
        legal = self._legal()
        if legal is None:
            return
        if kind == "fold":
            self.decision = Decision(Move.FOLD)
        elif kind == "call":
            self.decision = Decision(Move.CHECK if legal.can_check else Move.CALL)
        elif kind == "raise" and legal.can_raise:
            self.decision = Decision(legal.raise_move, self.raise_to or legal.min_to)

    # -- hand flow ---------------------------------------------------------------------------

    def _session(self):
        while True:
            if self.leaving:
                self._cash_out_and_go()
                return
            if self.room.stack == 0:
                self._busted()
                return
            changed = self.room.fill_seats()
            self._sync_seats()
            if changed:
                yield 0.6
            self.hand_wagered = 0
            yield from self._play(self.table.start_hand())
            while self.table.in_hand:
                seat = self.table.to_act
                if seat == HUMAN_SEAT:
                    decision = yield from self._await_human()
                else:
                    decision = yield from self._bot_turn(seat)
                yield from self._play(self.table.act(decision))
            self.mode = "between"
            self._sync_buttons()
            pause_until = self.t + 2.6 / self.app.anim_speed
            self.skip_pause = False
            while self.t < pause_until and not self.skip_pause and not self.leaving:
                yield None
            yield from self._clear_table()

    def _await_human(self):
        if self.leaving:
            return Decision(Move.FOLD)
        self.mode = "human"
        self.decision = None
        legal = self.table.legal()
        self._set_raise(legal.min_to)
        self.sound.play("ui_hover", 0.8)
        self._sync_buttons()
        while self.decision is None:
            yield None
        self.mode = "waiting"
        self._sync_buttons()
        return self.decision

    def _bot_turn(self, seat: int):
        self.mode = "bot"
        self._sync_buttons()
        self.active_seat = seat
        self.think_started = self.t
        human = self.table.players.get(HUMAN_SEAT)
        involved = human is not None and not human.folded and self.room.seated
        least = (self.app.rng.uniform(0.35, 0.9) if involved else 0.25) / self.app.anim_speed
        job = ai.think(self.table, seat, self.app.rng)
        decision: Decision | None = None
        while decision is None:
            deadline = time.perf_counter() + THINK_BUDGET
            try:
                while time.perf_counter() < deadline:
                    next(job)
            except StopIteration as done:
                decision = done.value
                break
            yield None
        while self.t - self.think_started < least:
            yield None
        self.active_seat = None
        return decision

    def _busted(self) -> None:
        self.room.cash_out()
        self.toast.show("You're out of chips. Buy in again to keep playing.", theme.GOLD)
        self._sync_seats()
        self._prepare_buyin()
        self._sync_buttons()

    # -- event playback ----------------------------------------------------------------------

    def _play(self, events: list):
        for event in events:
            handler = getattr(self, f"_on_{_snake(type(event).__name__)}", None)
            if handler is not None:
                result = handler(event)
                if result is not None:
                    yield from result

    def _on_hand_started(self, e: pk.HandStarted):
        for view in self.seats:
            view.in_hand = view.index in e.seats
            view.folded = view.all_in = False
            view.label = view.hand_desc = ""
            view.winner = 0.0
            view.bet = 0
        self.street_label = ""
        target = self.seats[e.button].button_pos
        yield self.anim.to(self, "button_pos", target, 0.35, ease_in_out_cubic)

    def _label(self, seat: int, text: str) -> None:
        view = self.seats[seat]
        view.label = text
        view.label_age = 0.0

    def _chips_to_bet(self, seat: int, added: Cents):
        view = self.seats[seat]
        if added <= 0:
            return None
        chips = Chips(added, view.avatar)
        self.flying.append(chips)
        view.stack -= added

        def land() -> None:
            self.flying.remove(chips)
            view.bet += added

        return self.anim.to(chips, "pos", view.bet_pos, 0.28, ease_out_cubic, on_done=land)

    def _on_blind_posted(self, e: pk.BlindPosted):
        if e.seat == HUMAN_SEAT:
            self.hand_wagered += e.amount
        self._label(e.seat, "SB" if e.kind == "small" else "BB")
        self.sound.play("chip_clack", 0.6)
        tween = self._chips_to_bet(e.seat, e.amount)
        if e.all_in:
            self.seats[e.seat].all_in = True
        yield tween or 0.0
        yield 0.1

    def _on_hole_cards(self, e: pk.HoleCards):
        # Cards are dealt one at a time round the table; HoleCards events arrive in
        # deal order, so deal the first card now and the second on a second pass.
        view = self.seats[e.seat]
        view.cards = []
        self._pending_holes.append(e)
        live = [v for v in self.seats if v.in_hand]
        if len(self._pending_holes) < len(live):
            return None
        holes, self._pending_holes = self._pending_holes, []
        return self._deal_holes(holes)

    def _deal_holes(self, holes: list[pk.HoleCards]):
        self.sound.play("shuffle", 0.5)
        yield 0.4
        for round_ in range(2):
            for e in holes:
                view = self.seats[e.seat]
                width = HUMAN_CARD_W if view.human else BOT_CARD_W
                sprite = CardSprite(e.cards[round_], DECK_POS, width, angle=20)
                view.cards.append(sprite)
                self.anim.to(sprite, "pos", view.card_pos(round_), 0.25, ease_out_cubic)
                self.anim.to(sprite, "angle", -6 + 12 * round_ if not view.human else 0, 0.25)
                if view.human:
                    self.anim.to(sprite, "flip", 1.0, 0.25, delay=0.25)
                self.sound.play("card_deal", 0.7, pan=(view.avatar[0] - 640) / 640)
                yield 0.09
        yield 0.3

    def _on_to_act(self, e: pk.ToAct):
        self.active_seat = e.seat
        return None

    def _on_acted(self, e: pk.Acted):
        view = self.seats[e.seat]
        if e.seat == HUMAN_SEAT:
            self.hand_wagered += e.added
        if e.move is Move.FOLD:
            view.folded = True
            self._label(e.seat, "FOLD")
            self.sound.play("card_flip", 0.6)
            for sprite in view.cards:
                self.anim.to(sprite, "pos", DECK_POS, 0.35, ease_in_out_cubic)
                self.anim.to(sprite, "alpha", 0.0, 0.35)
                if view.human:
                    self.anim.to(sprite, "flip", 0.0, 0.2)
            yield 0.3
            return
        if e.move is Move.CHECK:
            self._label(e.seat, "CHECK")
            self.sound.play("ui_click", 0.8)
            yield 0.25
            return
        text = {Move.CALL: "CALL", Move.BET: "BET", Move.RAISE: "RAISE"}[e.move]
        if e.all_in:
            text = "ALL IN"
            view.all_in = True
        elif e.move is not Move.CALL:
            text = f"{text} {fmt(e.bet)}"
        self._label(e.seat, text)
        self.sound.play("chip_cascade" if e.all_in else "chip_stack", 0.8)
        tween = self._chips_to_bet(e.seat, e.added)
        if e.all_in:
            self.particles.burst(view.avatar, 26, (theme.PINK, theme.GOLD), speed=(80, 260))
        yield tween or 0.0
        yield 0.15

    def _on_uncalled_returned(self, e: pk.UncalledReturned):
        view = self.seats[e.seat]
        view.bet -= e.amount
        view.stack += e.amount
        if e.seat == HUMAN_SEAT:
            self.hand_wagered -= e.amount
        return None

    def _on_bets_collected(self, e: pk.BetsCollected):
        moving = []
        for view in self.seats:
            if view.bet > 0:
                chips = Chips(view.bet, view.bet_pos)
                self.flying.append(chips)
                moving.append(self.anim.to(chips, "pos", POT_POS, 0.35, ease_in_out_cubic))
                view.bet = 0
        if moving:
            self.sound.play("chip_stack", 0.6)
            yield moving
        self.flying = [c for c in self.flying if c.pos != POT_POS]
        self.pot = e.pot

    def _on_board_dealt(self, e: pk.BoardDealt):
        for view in self.seats:
            if not view.folded and not view.all_in:
                view.label = ""
        self.street_label = e.street.value.upper()
        self.toast.show(e.street.value, theme.CYAN)
        yield 0.2
        for card in e.cards:
            i = len(self.board)
            target = (640 + (i - 2) * (BOARD_W + 12), BOARD_Y)
            sprite = CardSprite(card, DECK_POS, BOARD_W)
            self.board.append(sprite)
            self.sound.play("card_deal", 0.7)
            self.anim.to(sprite, "pos", target, 0.25, ease_out_cubic)
            self.anim.to(sprite, "flip", 1.0, 0.2, delay=0.18)
            yield 0.16
        yield 0.35

    def _on_showdown(self, e: pk.Showdown):
        self.street_label = "SHOWDOWN"
        for hand in e.hands:
            view = self.seats[hand.seat]
            view.hand_desc = hand.description
            view.label = ""
            for sprite in view.cards:
                if sprite.flip < 1.0:
                    self.sound.play("card_flip", 0.7)
                    self.anim.to(sprite, "flip", 1.0, 0.3)
                    self.anim.to(sprite, "scale", 1.35, 0.3, ease_out_back)
            yield 0.35
        yield 0.5
        self._showdown_best = {h.seat: h.best for h in e.hands}

    def _on_pot_awarded(self, e: pk.PotAwarded):
        best = self._showdown_best
        winners_best = {c for s in e.winners for c in best.get(s, ())}
        for sprite in [*self.board, *(c for s in e.winners for c in self.seats[s].cards)]:
            if sprite.card in winners_best:
                sprite.highlight = theme.GOLD
        moving = []
        for seat, share in zip(e.winners, e.shares, strict=True):
            view = self.seats[seat]
            view.winner = 1.0
            chips = Chips(share, POT_POS)
            self.flying.append(chips)

            def land(view=view, share=share, chips=chips) -> None:
                view.stack += share
                if chips in self.flying:
                    self.flying.remove(chips)

            moving.append(
                self.anim.to(chips, "pos", view.avatar, 0.6, ease_in_out_cubic, on_done=land)
            )
        self.pot = max(0, self.pot - e.amount)
        names = " & ".join("You" if s == HUMAN_SEAT else self.seats[s].name for s in e.winners)
        verb = "win" if HUMAN_SEAT in e.winners and len(e.winners) == 1 else "wins"
        if len(e.winners) > 1:
            verb = "split"
        pot_name = "the pot" if e.index == 0 else f"side pot {e.index}"
        sub = e.description
        human_won = HUMAN_SEAT in e.winners
        color = theme.GOLD if human_won else theme.TEXT
        self.banner.show(
            f"{names} {verb} {fmt(e.amount)}", sub, color, 1.6, center=(640, 392), size=38
        )
        if pot_name != "the pot":
            self.toast.show(f"{pot_name.capitalize()}: {fmt(e.amount)}", theme.TEXT)
        self.sound.play("chip_cascade" if e.amount >= 50 * BIG_BLIND else "chip_stack")
        if human_won:
            big = e.amount >= 60 * BIG_BLIND
            self.sound.play("win_big" if big else "win")
            self.marquee.celebrate(3.5 if big else 1.5)
            self.particles.burst(self.seats[HUMAN_SEAT].avatar, 40, (theme.GOLD, theme.WARM_WHITE))
            if big:
                self.particles.confetti(pygame.Rect(0, 0, theme.WIDTH, 40), 140)
        yield moving
        yield 0.8

    def _on_hand_over(self, e: pk.HandOver):
        self.pot = 0
        self.active_seat = None
        for view in self.seats:
            view.stack = e.stacks[view.index]
        if self.seats[HUMAN_SEAT].in_hand:
            net = e.net[HUMAN_SEAT]
            self.app.casino.record_round("poker", self.hand_wagered, self.hand_wagered + net)
        self.app.save()
        return None

    def _clear_table(self):
        sprites = [*self.board, *(c for v in self.seats for c in v.cards)]
        for sprite in sprites:
            sprite.highlight = None
            self.anim.to(sprite, "pos", DECK_POS, 0.35, ease_in_out_cubic)
            self.anim.to(sprite, "alpha", 0.0, 0.35)
        if sprites:
            self.sound.play("card_deal", 0.4)
            yield 0.4
        self.board.clear()
        for view in self.seats:
            view.cards.clear()
            view.label = view.hand_desc = ""
            view.winner = 0.0
        self._showdown_best = {}
        self.street_label = ""

    # -- frame ---------------------------------------------------------------------------

    def _sync_buttons(self) -> None:
        buyin = self.mode == "buyin"
        human = self.mode == "human"
        self.btn_sit.visible = self.btn_leave_dialog.visible = buyin
        low, high = getattr(self, "buyin_range", (MIN_BUY_IN, 0))
        self.btn_sit.enabled = buyin and high >= low
        legal = self._legal() if human else None
        for b in (self.btn_fold, self.btn_call, self.btn_raise, self.btn_allin, *self.quick):
            b.visible = human
        if legal is not None:
            self.btn_fold.enabled = True
            self.btn_call.label = "CHECK" if legal.can_check else f"CALL {fmt(legal.to_call)}"
            self.btn_raise.enabled = legal.can_raise
            word = "BET" if legal.current_bet == 0 else "RAISE"
            all_in = self.raise_to >= legal.max_to
            self.btn_raise.label = "ALL IN" if all_in else f"{word} {fmt(self.raise_to)}"
            for b in (*self.quick, self.btn_allin):
                b.enabled = legal.can_raise
        self.btn_topup.visible = self.room.seated and self.mode in ("between", "waiting", "bot")
        self.btn_topup.enabled = (
            not self.table.in_hand
            and self.room.buy_in_range()[1] >= CHIP
            and self.mode == "between"
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.leave()
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.mode == "between":
            self.skip_pause = True
            return True
        if super().handle_event(event):
            return True
        if self.mode == "buyin" and self.buyin_slider.handle_event(event):
            return True
        if self.mode == "human":
            if self.raise_slider.handle_event(event):
                return True
            if event.type == pygame.MOUSEWHEEL:
                legal = self._legal()
                if legal is not None:
                    self._set_raise(self.raise_to + event.y * BIG_BLIND)
                return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        self.marquee.update(dt)
        self.balance.set(self.app.casino.balance)
        self.balance.update(dt)
        for view in self.seats:
            view.label_age += dt
            view.winner = max(0.0, view.winner - dt * 0.4)
        self._sync_buttons()

    # -- drawing -------------------------------------------------------------------------

    def _draw_seat(self, surface: pygame.Surface, view: SeatView) -> None:
        if not view.present:
            return
        x, y = view.avatar
        fade = view.fade
        dim = view.folded or (not view.in_hand and self.table.in_hand)
        ring = view.color if not dim else (90, 80, 110)
        active = self.active_seat == view.index
        plate = pygame.Rect(0, 0, 176, 58)
        plate.center = (round(x), round(y + (6 if view.human else 34)))
        if view.human:
            plate.width = 220
            plate.center = (round(x), round(y + 10))
        fill = (14, 8, 30, round(225 * fade))
        draw_panel(surface, plate, fill, ring if active else (70, 60, 100), 14, 2)
        if active:
            pulse = 0.6 + 0.4 * math.sin(self.t * 7)
            pygame.draw.rect(
                surface,
                lerp_color(ring, theme.WHITE, pulse * 0.3),
                plate.inflate(6, 6),
                3,
                border_radius=16,
            )
        # Avatar disc with initials.
        if not view.human:
            pygame.draw.circle(surface, (10, 6, 20), (x, y), 30)
            pygame.draw.circle(surface, ring, (x, y), 30, 3)
            initials = "".join(w[0] for w in view.name.split()[:2]).upper()
            text = fonts.get("display", 20).render(initials, True, ring)
            surface.blit(text, text.get_rect(center=(x, y)))
        name_font = fonts.get("body_bold", 18)
        stack_font = fonts.get("display", 17)
        name = name_font.render(view.name, True, theme.TEXT if not dim else theme.TEXT_MUTED)
        stack_text = "ALL IN" if view.all_in and view.stack == 0 else fmt(view.stack)
        stack = stack_font.render(stack_text, True, theme.GOLD if not dim else theme.TEXT_MUTED)
        if view.human:
            surface.blit(name, name.get_rect(midleft=(plate.left + 16, plate.centery)))
            surface.blit(stack, stack.get_rect(midright=(plate.right - 16, plate.centery)))
        else:
            surface.blit(name, name.get_rect(center=(plate.centerx, plate.top + 18)))
            surface.blit(stack, stack.get_rect(center=(plate.centerx, plate.top + 40)))
        if view.profile and not view.human:
            tag = fonts.get("body", 14).render(view.profile.upper(), True, theme.TEXT_MUTED)
            surface.blit(tag, tag.get_rect(center=(x, y - 40)))
        # Thinking dots.
        if active and not view.human and self.mode == "bot":
            dots = int(self.t * 4) % 4
            text = fonts.get("display", 18).render("." * dots, True, ring)
            surface.blit(text, text.get_rect(midleft=(x + 34, y - 10)))
        if view.winner > 0:
            halo = neon_text("WINNER", "display", 18, theme.GOLD, 8)
            halo.draw(surface, (plate.centerx, plate.bottom + 14), min(1.0, view.winner * 2))

    def _draw_labels(self, surface: pygame.Surface) -> None:
        for view in self.seats:
            if view.label and view.present:
                key = view.label.split(" ")[0] if not view.label.startswith("ALL") else "ALL IN"
                color = ACTION_COLORS.get(key, theme.TEXT)
                pop = ease_out_back(min(1.0, view.label_age / 0.25))
                pos = view.label_pos
                text = fonts.get("display", 16).render(view.label, True, theme.WHITE)
                box = text.get_rect(center=pos).inflate(18, 8)
                box = box.inflate(-(1 - pop) * box.width, -(1 - pop) * box.height)
                draw_panel(surface, box, (*color, 235), None, 10)
                if pop > 0.9:
                    surface.blit(text, text.get_rect(center=box.center))
            if view.hand_desc and view.present:
                if view.human:
                    center = (640, 592)
                else:
                    cx, cy = view.card_pos(0)
                    above = view.index in (1, 5)  # lower side seats: keep clear of the plate
                    center = (cx + 14, cy - 58 if above else cy + 50)
                text = fonts.get("body_bold", 17).render(view.hand_desc, True, theme.WARM_WHITE)
                box = text.get_rect(center=center).inflate(14, 4)
                draw_panel(surface, box, (8, 4, 20, 220), theme.GOLD, 8, 1)
                surface.blit(text, text.get_rect(center=box.center))

    def _draw_chips(self, surface: pygame.Surface, chips: Chips) -> None:
        if chips.amount > 0 and chips.alpha > 0.02:
            draw_amount(surface, chips.amount, (chips.pos[0], chips.pos[1] + 10), CHIP_D, 8)

    def _draw_table_state(self, surface: pygame.Surface) -> None:
        # Bets in front of players.
        font = fonts.get("display", 14)
        for view in self.seats:
            if view.bet > 0:
                bx, by = view.bet_pos
                draw_amount(surface, view.bet, (bx, by + 10), CHIP_D, 6)
                text = font.render(fmt(view.bet), True, theme.WHITE)
                box = text.get_rect(center=(bx, by + 24)).inflate(10, 2)
                draw_panel(surface, box, (0, 0, 0, 170), None, 6)
                surface.blit(text, text.get_rect(center=box.center))
        # Pot.
        if self.pot > 0:
            draw_amount(surface, self.pot, (POT_POS[0], POT_POS[1] + 4), CHIP_D, 8)
            text = fonts.get("display", 18).render(f"POT {fmt(self.pot)}", True, theme.GOLD)
            surface.blit(text, text.get_rect(center=(POT_POS[0], POT_POS[1] - 44)))
        # Dealer button.
        bx, by = self.button_pos
        if self.table.hand_number:
            pygame.draw.circle(surface, (0, 0, 0), (bx + 2, by + 3), 14)
            pygame.draw.circle(surface, theme.WARM_WHITE, (bx, by), 14)
            pygame.draw.circle(surface, (150, 150, 150), (bx, by), 14, 2)
            d = fonts.get("display", 15).render("D", True, (20, 20, 30))
            surface.blit(d, d.get_rect(center=(bx, by + 1)))

    def _draw_buyin(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect(390, 200, 500, 320)
        draw_panel(surface, panel, (16, 8, 34, 245), theme.GOLD, 20, 3)
        title = neon_text("TAKE A SEAT", "display", 34, theme.GOLD, 10)
        title.draw(surface, (640, 250))
        info = fonts.get("body_bold", 20).render(
            "No-Limit Hold'em  ·  Blinds $5/$10  ·  Buy-in $400 - $2,000", True, theme.TEXT_DIM
        )
        surface.blit(info, info.get_rect(center=(640, 296)))
        low, high = self.buyin_range
        if high < low:
            msg = fonts.get("body_bold", 22).render(
                f"You need at least {fmt(MIN_BUY_IN)} to sit down.", True, theme.LOSE
            )
            surface.blit(msg, msg.get_rect(center=(640, 370)))
            return
        amount = fonts.get("display", 34).render(fmt(self.buyin_amount), True, theme.WHITE)
        surface.blit(amount, amount.get_rect(center=(640, 344)))
        self.buyin_slider.draw(surface)

    def _draw_action_panel(self, surface: pygame.Surface) -> None:
        if self.mode != "human":
            return
        draw_panel(surface, pygame.Rect(866, 552, 404, 162), (10, 6, 24, 225), theme.GOLD, 16)
        legal = self._legal()
        if legal is not None and legal.can_raise:
            self.raise_slider.draw(surface)
        prompt = fonts.get("body_bold", 18).render("YOUR MOVE", True, theme.GOLD)
        surface.blit(prompt, (884, 562))

    def _draw_info(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(22, 620, 330, 88)
        draw_panel(surface, panel, (8, 4, 20, 200), theme.PURPLE, 14)
        self.balance.draw(surface)
        hand = self.table.hand_number
        info = fonts.get("body", 16).render(
            f"Hand #{hand}" if hand else "Not seated yet", True, theme.TEXT_MUTED
        )
        surface.blit(info, (230, 632))
        if self.street_label:
            street = fonts.get("display", 16).render(self.street_label, True, theme.CYAN)
            surface.blit(street, (230, 656))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        self.marquee.draw(surface)
        for view in self.seats:
            self._draw_seat(surface, view)
        self._draw_table_state(surface)
        for sprite in self.board:
            sprite.draw(surface)
        for view in self.seats:
            for sprite in view.cards:
                sprite.draw(surface)
        for chips in self.flying:
            self._draw_chips(surface, chips)
        self._draw_labels(surface)
        self._draw_info(surface)
        self._draw_action_panel(surface)
        if self.mode == "buyin":
            self._draw_buyin(surface)
        self.draw_buttons(surface)
        self.draw_overlays(surface)
