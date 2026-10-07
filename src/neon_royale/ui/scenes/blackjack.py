"""Blackjack table: bet, deal from the shoe, play your hands, watch the dealer."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from ...core import blackjack as bj
from ...core.blackjack import Action, BlackjackTable, Outcome, Phase, RuleError
from ...core.money import Cents, fmt
from .. import fonts, theme
from ..caches import optimise
from ..fx.tween import ease_in_out_cubic, ease_out_back, ease_out_cubic
from ..render.cards import card_back
from ..render.chips import draw_amount
from ..render.decor import (
    draw_gilded_frame,
    engraved_text,
    lacquer_panel,
    padded_ellipse,
    table_background,
    wood,
)
from ..sprites import CardSprite
from ..stage import Stage
from ..theme import Color
from ..widgets import ChipRack, CountingLabel, draw_panel

CARD_W = 92
SHOE_POS = (1150, 158)
DISCARD_POS = (130, 196)
DEALER_Y = 165
HAND_Y = 415
BET_Y = 548
ARC_CENTER = (640, -420)
BANNER_AT = (640, 262)
ARC_RADIUS = 690
BALANCE_POS = (62, 676)
DEALER_CHIPS = (640, 72)

OUTCOME_STYLE: dict[Outcome, tuple[str, Color]] = {
    Outcome.BLACKJACK: ("BLACKJACK!", theme.GOLD),
    Outcome.WIN: ("WIN", theme.WIN),
    Outcome.PUSH: ("PUSH", theme.PUSH),
    Outcome.LOSE: ("LOSE", theme.LOSE),
    Outcome.BUST: ("BUST", theme.LOSE),
    Outcome.SURRENDER: ("SURRENDER", theme.TEXT_DIM),
}


@dataclass
class Stack:
    """Chips sitting in (or moving around) a betting circle."""

    amount: Cents
    pos: tuple[float, float]
    alpha: float = 1.0


def _arc_text(
    surface: pygame.Surface,
    text: str,
    center: tuple[float, float],
    radius: float,
    font: pygame.font.Font,
    color: Color,
    spacing: float = 1.0,
) -> None:
    """Print ``text`` along the bottom of a circle, reading left to right."""
    widths = [font.size(ch)[0] * spacing for ch in text]
    total = sum(widths)
    angle = math.pi / 2 + (total / 2) / radius  # start left of bottom-centre
    for ch, w in zip(text, widths, strict=True):
        a = angle - (w / 2) / radius
        glyph = font.render(ch, True, color)
        glyph = pygame.transform.rotozoom(glyph, math.degrees(a - math.pi / 2), 1.0)
        x = center[0] + math.cos(a) * radius
        y = center[1] + math.sin(a) * radius
        surface.blit(glyph, glyph.get_rect(center=(x, y)))
        angle -= w / radius


ARMREST = pygame.Rect(-380, 604, 2040, 1400)  # the padded rail along the player side

CHIP_TRAY_COLORS = (
    (236, 236, 240),
    (206, 30, 44),
    (20, 140, 74),
    (30, 30, 38),
    (114, 46, 182),
    (246, 182, 32),
)


def _chip_tray(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """The dealer's float: rows of chips lying in a wooden tray."""
    surface.blit(wood(rect.size, theme.WALNUT, 3), rect)
    pygame.draw.rect(surface, (10, 4, 2), rect, 3, border_radius=8)
    slots = 12
    slot_w = (rect.width - 20) / slots
    for i in range(slots):
        color = CHIP_TRAY_COLORS[(i // 2) % len(CHIP_TRAY_COLORS)]
        slot = pygame.Rect(0, 0, slot_w - 6, rect.height - 16)
        slot.topleft = (rect.left + 10 + i * slot_w + 3, rect.top + 8)
        pygame.draw.rect(surface, (14, 6, 2), slot.inflate(4, 4), border_radius=6)
        pygame.draw.rect(surface, color, slot, border_radius=5)
        edge = theme.scale_color(color, 0.65)
        for y in range(slot.top + 3, slot.bottom - 2, 5):
            pygame.draw.line(surface, edge, (slot.left + 2, y), (slot.right - 3, y), 1)
        pygame.draw.line(
            surface,
            (255, 255, 255),
            (slot.left + 3, slot.top + 2),
            (slot.left + 3, slot.bottom - 3),
            1,
        )
    draw_gilded_frame(surface, rect.inflate(6, 6), 2, 10)


def _box(surface: pygame.Surface, center: tuple[int, int], label: str) -> pygame.Rect:
    box = pygame.Rect(0, 0, 124, 152)
    box.center = center
    shadow = pygame.Surface((box.width + 30, box.height + 30), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 150), shadow.get_rect().inflate(-24, -24), border_radius=16)
    surface.blit(pygame.transform.box_blur(shadow, 8), (box.left - 9, box.top - 6))
    lacquer_panel(surface, box, (70, 10, 18), 255, True, 14)
    text = fonts.get("body_bold", 12).render(" ".join(label), True, theme.GOLD)
    surface.blit(text, text.get_rect(center=(box.centerx, box.bottom - 12)))
    return box


def render_table() -> pygame.Surface:
    surf = table_background(theme.FELT_GREEN, theme.FELT_GREEN_DARK, seed=21).copy()
    print_color = (236, 224, 190)
    pygame.draw.circle(surf, theme.GOLD, ARC_CENTER, ARC_RADIUS, 2)
    pygame.draw.circle(surf, theme.GOLD_DARK, ARC_CENTER, ARC_RADIUS + 110, 1)
    _arc_text(
        surf,
        "BLACKJACK PAYS 3 TO 2",
        ARC_CENTER,
        ARC_RADIUS + 34,
        fonts.get("display", 30),
        theme.GOLD_LIGHT,
        1.06,
    )
    _arc_text(
        surf,
        "DEALER MUST STAND ON ALL 17s  ·  INSURANCE PAYS 2 TO 1",
        ARC_CENTER,
        ARC_RADIUS + 80,
        fonts.get("body_bold", 21),
        print_color,
        1.06,
    )
    _chip_tray(surf, pygame.Rect(430, 34, 420, 54))
    _box(surf, SHOE_POS, "SHOE")
    back = card_back(CARD_W)
    for i in range(4):
        surf.blit(back, back.get_rect(center=(SHOE_POS[0] - 6 + i * 3, SHOE_POS[1] - 8 - i * 2)))
    _box(surf, DISCARD_POS, "DISCARDS")
    # Padded leather armrest on the player's side.
    pygame.draw.ellipse(surf, (16, 10, 8), ARMREST)
    padded_ellipse(surf, ARMREST, 30)
    pygame.draw.ellipse(surf, theme.GOLD_DARK, ARMREST.inflate(-62, -62), 1)
    return optimise(surf)


class BlackjackScene(Stage):
    help_topic = "blackjack"
    ambience = 0.45

    def shutdown(self) -> None:
        self.table.abandon()

    def enter(self) -> None:
        app = self.app
        self.table = BlackjackTable(app.casino.wallet, app.rng)
        self.background = render_table()
        self.rack = ChipRack((640, 652), self.sound, diameter=52)
        self.balance = CountingLabel(BALANCE_POS, app.casino.balance, "Bankroll", "midleft", 32)
        self.toast.y = 262  # between the dealer's cards and the player's

        self.dealer_cards: list[CardSprite] = []
        self.hand_cards: list[list[CardSprite]] = []
        self.stacks: list[Stack] = []
        self.flying: list[Stack] = []
        self.labels: dict[int, tuple[str, Color, float]] = {}
        self.outcomes: dict[int, Outcome] = {}
        self.sideways_next: set[int] = set()
        self.bet_chips: list[Cents] = []
        self.mode = "betting"  # betting | dealing | insurance | player | done
        self.round_net: Cents = 0

        y = 622
        b = self.button
        # Betting.
        self.btn_clear = b((870, y, 120, 52), "CLEAR", self.clear_bet, hotkey=pygame.K_c)
        self.btn_deal = b(
            (1006, y - 6, 220, 64),
            "DEAL",
            self.deal,
            kind="primary",
            font_size=30,
            hotkey=pygame.K_SPACE,
        )
        # Player decisions.
        actions = (
            ("HIT", Action.HIT, pygame.K_h, "primary"),
            ("STAND", Action.STAND, pygame.K_s, "primary"),
            ("DOUBLE", Action.DOUBLE, pygame.K_d, "secondary"),
            ("SPLIT", Action.SPLIT, pygame.K_p, "secondary"),
            ("SURRENDER", Action.SURRENDER, pygame.K_r, "danger"),
        )
        self.action_buttons: dict[Action, object] = {}
        x = 330
        for label, action, key, color in actions:
            width = 168 if action is Action.SURRENDER else 132
            self.action_buttons[action] = b(
                (x, y, width, 54),
                label,
                lambda a=action: self.act(a),
                kind=color,
                hotkey=key,
                font_size=21,
            )
            x += width + 12
        self.btn_hint = b(
            (x, y, 110, 54),
            "HINT",
            self.hint,
            hotkey=pygame.K_QUESTION,
            font_size=20,
        )
        # Insurance.
        self.btn_insure = b(
            (430, y, 250, 54),
            "INSURANCE",
            self.insure,
            kind="primary",
            hotkey=pygame.K_i,
            font_size=22,
        )
        self.btn_no_insure = b(
            (700, y, 250, 54),
            "NO THANKS",
            self.no_insurance,
            hotkey=pygame.K_n,
            font_size=22,
        )
        self.button((40, 38, 130, 44), "LOBBY", self.leave, font_size=18)
        self.add_help_button()

        if self.table.last_bet:
            self.bet_chips = [self.table.last_bet]
        self._sync_buttons()

    # -- bankroll shown = wallet minus the bet waiting in the circle ----------------------

    @property
    def pending_bet(self) -> Cents:
        return sum(self.bet_chips)

    def _refresh_balance(self) -> None:
        shown = self.table.wallet.balance - (self.pending_bet if self.mode == "betting" else 0)
        self.balance.set(shown)
        self.rack.set_balance(shown)

    # -- betting --------------------------------------------------------------------------

    def _refuse(self, message: str) -> None:
        self.sound.play("ui_error", 0.7)
        self.toast.show(message, theme.LOSE)

    def add_chip(self) -> None:
        if self.mode != "betting":
            return
        chip = self.rack.value
        total = self.pending_bet + chip
        if total > self.table.max_bet:
            self._refuse(f"Table maximum is {fmt(self.table.max_bet)}")
            return
        if total > self.table.wallet.balance:
            self._refuse("Not enough chips")
            return
        self.bet_chips.append(chip)
        self.sound.play("chip_clack", 0.8)
        self._refresh_balance()

    def remove_chip(self) -> None:
        if self.mode == "betting" and self.bet_chips:
            self.bet_chips.pop()
            self.sound.play("chip_clack", 0.5)
            self._refresh_balance()

    def clear_bet(self) -> None:
        if self.mode == "betting" and self.bet_chips:
            self.bet_chips.clear()
            self.sound.play("chip_stack", 0.6)
            self._refresh_balance()

    def deal(self) -> None:
        if self.mode != "betting":
            return
        bet = self.pending_bet
        if bet < self.table.min_bet:
            self._refuse(f"Minimum bet is {fmt(self.table.min_bet)}: click the circle to bet")
            return
        try:
            events = self.table.deal(bet)
        except RuleError as exc:
            self._refuse(str(exc).capitalize())
            return
        self.mode = "dealing"
        self.labels.clear()
        self.outcomes.clear()
        self.stacks = [Stack(bet, (640, BET_Y))]
        self.hand_cards = [[]]
        self.dealer_cards = []
        self.sideways_next.clear()
        self._refresh_balance()
        self.director.run(self._play(events))

    # -- decisions ------------------------------------------------------------------------

    def act(self, action: Action) -> None:
        if self.mode != "player" or action not in self.table.legal_actions():
            return
        if action is Action.DOUBLE:
            self.sideways_next.add(self.table.active)
        self.mode = "dealing"
        self.director.run(self._play(self.table.act(action)))

    def insure(self) -> None:
        if self.mode == "insurance":
            self.mode = "dealing"
            try:
                events = self.table.take_insurance()
            except RuleError as exc:
                self.mode = "insurance"
                self._refuse(str(exc).capitalize())
                return
            self._refresh_balance()
            self.director.run(self._play(events))

    def no_insurance(self) -> None:
        if self.mode == "insurance":
            self.mode = "dealing"
            self.director.run(self._play(self.table.decline_insurance()))

    def hint(self) -> None:
        if self.mode != "player":
            return
        best = bj.basic_strategy(self.table.hand, self.table.upcard, self.table.legal_actions())
        self.sound.play("ui_click")
        self.toast.show(f"Basic strategy says: {best.value.upper()}", theme.GOLD_LIGHT)

    def leave(self) -> None:
        if self.mode not in ("betting",):
            self._refuse("Finish the hand first")
            return
        self.app.save()
        self.app.go("lobby")

    # -- layout -------------------------------------------------------------------------

    def hand_x(self, index: int, count: int | None = None) -> float:
        count = count if count is not None else max(1, len(self.hand_cards))
        spacing = 250 if count > 2 else 300
        return 640 + (index - (count - 1) / 2) * spacing

    def player_slot(self, hand: int, card: int, count: int | None = None) -> tuple[float, float]:
        x = self.hand_x(hand, count)
        return x - 16 + card * 26, HAND_Y - card * 16

    def dealer_slot(self, card: int) -> tuple[float, float]:
        n = max(2, len(self.dealer_cards))
        return 640 + (card - (n - 1) / 2) * 62, DEALER_Y

    def _relayout(self, duration: float = 0.3):
        count = len(self.hand_cards)
        tweens = []
        for h, sprites in enumerate(self.hand_cards):
            for c, sprite in enumerate(sprites):
                tweens.append(
                    self.anim.to(
                        sprite, "pos", self.player_slot(h, c, count), duration, ease_in_out_cubic
                    )
                )
        for h, stack in enumerate(self.stacks):
            tweens.append(
                self.anim.to(
                    stack, "pos", (self.hand_x(h, count), BET_Y), duration, ease_in_out_cubic
                )
            )
        for c, sprite in enumerate(self.dealer_cards):
            tweens.append(self.anim.to(sprite, "pos", self.dealer_slot(c), duration))
        return tweens

    # -- event playback -----------------------------------------------------------------

    def _deal_card(self, event: bj.CardDealt):
        sprite = CardSprite(event.card, SHOE_POS, CARD_W, face_up=False, angle=12)
        if event.to == "dealer":
            self.dealer_cards.append(sprite)
            target = self.dealer_slot(len(self.dealer_cards) - 1)
            self._relayout(0.25)
        else:
            while len(self.hand_cards) <= event.hand:
                self.hand_cards.append([])
            cards_in_hand = self.hand_cards[event.hand]
            cards_in_hand.append(sprite)
            target = self.player_slot(event.hand, len(cards_in_hand) - 1)
        final_angle = 0.0
        if event.to == "player" and event.hand in self.sideways_next:
            final_angle = 90.0
            self.sideways_next.discard(event.hand)
        self.sound.play("card_deal", 0.9, pan=(target[0] - 640) / 640)
        self.anim.to(sprite, "pos", target, 0.3, ease_out_cubic)
        self.anim.to(sprite, "angle", final_angle, 0.3, ease_out_cubic)
        if event.face_up:
            self.anim.to(sprite, "flip", 1.0, 0.22, delay=0.08)
        yield 0.26

    def _play(self, events: list):
        """Animate engine events in order, then hand control back to the player."""
        for event in events:
            if isinstance(event, bj.Shuffled):
                self.toast.show("Shuffling a fresh shoe…", theme.GOLD_LIGHT)
                self.sound.play("shuffle")
                yield 1.1
            elif isinstance(event, bj.CardDealt):
                yield from self._deal_card(event)
            elif isinstance(event, bj.HoleRevealed):
                hole = self.dealer_cards[1]
                self.sound.play("card_flip")
                yield self.anim.to(hole, "flip", 1.0, 0.3, ease_in_out_cubic)
                yield 0.25
            elif isinstance(event, bj.InsuranceOffered):
                self.mode = "insurance"
                even = self.table.hands[0].is_blackjack
                self.btn_insure.label = "EVEN MONEY" if even else f"INSURE {fmt(event.max_amount)}"
                prompt = "Even money?" if even else "Dealer shows an ace. Insurance?"
                self.toast.show(prompt, theme.GOLD)
            elif isinstance(event, bj.Peeked):
                hole = self.dealer_cards[1]
                self.toast.show("Dealer checks for blackjack…", theme.TEXT)
                yield self.anim.to(hole, "lift", 10.0, 0.18, ease_out_cubic)
                yield 0.3
                yield self.anim.to(hole, "lift", 0.0, 0.18)
                if not event.blackjack:
                    yield 0.1
            elif isinstance(event, bj.InsuranceSettled):
                if event.returned:
                    self.sound.play("chip_stack")
                    self.toast.show(f"Insurance pays {fmt(event.returned)}", theme.WIN)
                else:
                    self.toast.show("Insurance lost", theme.TEXT_DIM)
                self._refresh_balance()
                yield 0.4
            elif isinstance(event, bj.Split):
                yield from self._split(event)
            elif isinstance(event, bj.Doubled):
                self.stacks[event.hand].amount = event.bet
                self.sound.play("chip_stack", 0.8)
                self._refresh_balance()
                yield 0.2
            elif isinstance(event, bj.Surrendered):
                for sprite in self.hand_cards[event.hand]:
                    self.anim.to(sprite, "dim", 1.0, 0.3)
                yield 0.3
            elif isinstance(event, bj.TurnChanged):
                yield 0.12
            elif isinstance(event, bj.HandSettled):
                yield from self._settle_hand(event)
            elif isinstance(event, bj.RoundOver):
                yield from self._round_over(event)
                return
        if self.table.phase is Phase.PLAYER:
            self.mode = "player"
        self._sync_buttons()

    def _split(self, event: bj.Split):
        moved = self.hand_cards[event.hand].pop()
        self.hand_cards.insert(event.new_hand, [moved])
        bet = self.table.hands[event.new_hand].bet
        self.stacks.insert(event.new_hand, Stack(bet, self.stacks[event.hand].pos))
        self.sound.play("chip_stack", 0.8)
        self._refresh_balance()
        yield self._relayout(0.35)

    def _settle_hand(self, event: bj.HandSettled):
        text, color = OUTCOME_STYLE[event.outcome]
        stack = self.stacks[event.hand]
        cards = self.hand_cards[event.hand]
        winnings = event.returned - event.stake
        if winnings > 0:
            text += f"  +{fmt(winnings)}"
        self.labels[event.hand] = (text, color, 0.0)
        self.outcomes[event.hand] = event.outcome
        if event.outcome in (Outcome.WIN, Outcome.BLACKJACK):
            for sprite in cards:
                sprite.highlight = theme.GOLD
            paid = Stack(winnings, DEALER_CHIPS)
            self.flying.append(paid)
            target = (stack.pos[0] + 44, stack.pos[1])
            self.sound.play("chip_stack", 0.8)
            yield self.anim.to(paid, "pos", target, 0.35, ease_out_cubic)
            self.particles.burst(target, 20, (theme.GOLD, theme.WARM_WHITE), speed=(80, 240))
        elif event.outcome in (Outcome.LOSE, Outcome.BUST):
            self.anim.to(stack, "pos", DEALER_CHIPS, 0.4, ease_in_out_cubic)
            self.anim.to(stack, "alpha", 0.0, 0.4)
            for sprite in cards:
                self.anim.to(sprite, "dim", 1.0, 0.3)
            self.sound.play("chip_clack", 0.6)
        elif event.outcome is Outcome.SURRENDER:
            stack.amount = event.returned
        yield 0.3

    def _round_over(self, event: bj.RoundOver):
        self.round_net = event.net
        self.app.casino.record_round("blackjack", event.wagered, event.returned)
        outcomes = list(self.outcomes.values())
        yield 0.3
        # Collect: everything still on the felt goes to the player.
        to_player = [s for s in [*self.stacks, *self.flying] if s.alpha > 0.5]
        if event.returned:
            for s in to_player:
                self.anim.to(s, "pos", BALANCE_POS, 0.5, ease_in_out_cubic)
                self.anim.to(s, "alpha", 0.0, 0.5, ease_in_out_cubic)
            self.sound.play("chip_stack")
            yield 0.5
        self._refresh_balance()
        if Outcome.BLACKJACK in outcomes:
            self.sound.play("blackjack")
            self.celebrate(3.0, big=True)
            self.banner.show("BLACKJACK!", "", theme.GOLD, hold=1.6, center=BANNER_AT)
        elif event.net >= self.table.last_bet * 4 and event.net > 0:
            self.sound.play("win_big")
            self.celebrate(3.5, big=True)
            self.banner.show("BIG WIN!", "", theme.GOLD, hold=1.8, center=BANNER_AT)
        elif event.net > 0:
            self.sound.play("win")
            self.celebrate(1.2)
            self.banner.show("YOU WIN", "", theme.WIN, hold=1.2, center=BANNER_AT)
        elif event.net == 0 and event.returned:
            self.sound.play("push", 0.7)
            self.banner.show("PUSH", "", theme.PUSH, hold=1.0, center=BANNER_AT)
        else:
            self.sound.play("lose", 0.6)
            dealer_total = bj.hand_value(self.table.dealer)[0]
            if dealer_total == 21 and len(self.table.dealer) == 2:
                self.banner.show("DEALER BLACKJACK", "", theme.LOSE, hold=1.2, center=BANNER_AT)
        self.app.save()
        yield 2.0
        yield from self._clear_table()

    def _clear_table(self):
        sprites = [*self.dealer_cards, *(s for hand in self.hand_cards for s in hand)]
        for sprite in sprites:
            sprite.highlight = None
            self.anim.to(sprite, "pos", DISCARD_POS, 0.4, ease_in_out_cubic)
            self.anim.to(sprite, "flip", 0.0, 0.3)
            self.anim.to(sprite, "angle", 0.0, 0.3)
        self.sound.play("card_deal", 0.5)
        yield 0.45
        self.dealer_cards.clear()
        self.hand_cards.clear()
        self.stacks.clear()
        self.flying.clear()
        self.labels.clear()
        self.outcomes.clear()
        self.table.new_round()
        self.mode = "betting"
        last = self.table.last_bet
        self.bet_chips = [last] if last and last <= self.table.wallet.balance else []
        self._refresh_balance()
        self._sync_buttons()
        if self.app.casino.comp_available and not self.bet_chips:
            self.toast.show("Out of chips? The lobby has a gift for you.", theme.GOLD_LIGHT)

    # -- frame ----------------------------------------------------------------------------

    def _sync_buttons(self) -> None:
        betting = self.mode == "betting"
        player = self.mode == "player"
        insurance = self.mode == "insurance"
        self.btn_clear.visible = self.btn_deal.visible = betting
        self.btn_deal.enabled = betting and self.pending_bet >= self.table.min_bet
        self.btn_clear.enabled = betting and bool(self.bet_chips)
        legal = self.table.legal_actions() if player else set()
        for action, button in self.action_buttons.items():
            button.visible = player
            button.enabled = action in legal
        self.btn_hint.visible = player
        self.btn_insure.visible = self.btn_no_insure.visible = insurance

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.leave()
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.deal()
            return True
        if super().handle_event(event):
            self._sync_buttons()
            return True
        if self.mode == "betting":
            if self.rack.handle_event(event):
                return True
            if event.type == pygame.MOUSEBUTTONDOWN:
                circle = pygame.Vector2(640, BET_Y)
                if circle.distance_to(event.pos) <= 52:
                    if event.button == 1:
                        self.add_chip()
                    elif event.button == 3:
                        self.remove_chip()
                    self._sync_buttons()
                    return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        self.rack.update(dt)
        self.balance.update(dt)
        for key, (text, color, age) in list(self.labels.items()):
            self.labels[key] = (text, color, age + dt)
        self._sync_buttons()

    # -- drawing ----------------------------------------------------------------------------

    def _draw_bet_circles(self, surface: pygame.Surface) -> None:
        if self.mode == "betting":
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.t * 4)) if not self.bet_chips else 1.0
            pygame.draw.circle(surface, theme.GOLD, (640, BET_Y), 42, 3)
            pygame.draw.circle(surface, theme.GOLD_DARK, (640, BET_Y), 36, 1)
            ring = engraved_text("BET", "display", 20, "gold", shadow=2)
            if not self.bet_chips:
                ring.draw(surface, (640, BET_Y), pulse)
            else:
                draw_amount(surface, self.pending_bet, (640, BET_Y + 18), 40)
                amount = fonts.get("numbers", 22).render(fmt(self.pending_bet), True, theme.TEXT)
                surface.blit(amount, amount.get_rect(midleft=(700, BET_Y)))
            return
        for i in range(len(self.stacks)):
            x = self.hand_x(i)
            pygame.draw.circle(surface, theme.GOLD, (round(x), BET_Y), 40, 2)
            if i == self.table.active and self.mode == "player" and len(self.stacks) > 1:
                bob = 4 * math.sin(self.t * 6)
                tip = (x, BET_Y + 48 + bob)
                points = [tip, (tip[0] - 12, tip[1] + 16), (tip[0] + 12, tip[1] + 16)]
                pygame.draw.polygon(surface, theme.GOLD_LIGHT, points)
                pygame.draw.polygon(surface, theme.GOLD_DARK, points, 2)

    def _draw_stack(self, surface: pygame.Surface, stack: Stack) -> None:
        if stack.alpha <= 0.02 or stack.amount <= 0:
            return
        if stack.alpha >= 0.99:
            draw_amount(surface, stack.amount, (stack.pos[0], stack.pos[1] + 18), 40)
            return
        layer = pygame.Surface((200, 200), pygame.SRCALPHA)
        draw_amount(layer, stack.amount, (100, 150), 40)
        layer.set_alpha(round(255 * stack.alpha))
        surface.blit(layer, (stack.pos[0] - 100, stack.pos[1] + 18 - 150))

    def _draw_totals(self, surface: pygame.Surface) -> None:
        font = fonts.get("numbers", 19)
        if self.dealer_cards:
            total = bj.hand_value(
                [s.card for s in self.dealer_cards if s.flip >= 0.5 and s.card is not None]
            )[0]
            if total:
                right = 640 + 31 * (len(self.dealer_cards) - 1) + CARD_W // 2
                self._badge(surface, str(total), (right + 44, DEALER_Y), theme.TEXT, font)
        for i, sprites in enumerate(self.hand_cards):
            if i >= len(self.table.hands) or not sprites:
                continue
            hand = self.table.hands[i]
            shown = [s.card for s in sprites if s.card is not None and s.flip >= 0.5]
            if not shown:
                continue
            total, soft = bj.hand_value(shown)
            text = str(total) if not (soft and total < 21) else f"SOFT {total}"
            if len(shown) == 2 and total == 21 and not hand.from_split:
                text = "BJ"
            color = theme.LOSE if total > 21 else theme.TEXT
            active = i == self.table.active and self.mode == "player"
            self._badge(surface, text, (self.hand_x(i) - 16, HAND_Y + 76), color, font, active)

    def _badge(self, surface, text, center, color, font, glow: bool = False) -> None:
        label = font.render(text, True, color)
        box = label.get_rect(center=center).inflate(24, 10)
        lacquer_panel(surface, box, (18, 10, 6), 235, True, 10, glow=0.8 if glow else 0.0)
        surface.blit(label, label.get_rect(center=box.center))

    def _draw_labels(self, surface: pygame.Surface) -> None:
        for i, (text, color, age) in self.labels.items():
            pop = ease_out_back(min(1.0, age / 0.3))
            style = {theme.WIN: "emerald", theme.LOSE: "ruby"}.get(color, "gold")
            if color in (theme.TEXT_DIM, theme.TEXT):
                style = "cream"
            graphic = engraved_text(text, "display", 26, style, shadow=2)
            y = HAND_Y - 112 - 10 * (1 - pop)
            w, h = graphic.content_size
            pill = pygame.Rect(0, 0, w + 28, h + 6)
            pill.center = (round(self.hand_x(i)), round(y))
            draw_panel(surface, pill, (14, 8, 6, round(215 * min(1.0, age / 0.2))), None, 16)
            graphic.draw(surface, (self.hand_x(i), y), min(1.0, age / 0.2))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(40, 624, 268, 82)
        draw_panel(surface, panel, (20, 11, 7, 235), theme.GOLD, 14, 2)
        self.balance.draw(surface)
        info = fonts.get("body", 17).render(
            f"Bets {fmt(self.table.min_bet)} - {fmt(self.table.max_bet)}",
            True,
            theme.TEXT_MUTED,
        )
        surface.blit(info, info.get_rect(center=(SHOE_POS[0], SHOE_POS[1] + 120)))
        left = self.table.shoe.remaining
        shoe = fonts.get("body_bold", 17).render(f"{left} cards in shoe", True, theme.TEXT_DIM)
        surface.blit(shoe, shoe.get_rect(center=(SHOE_POS[0], SHOE_POS[1] + 96)))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        self._draw_bet_circles(surface)
        for stack in self.stacks:
            self._draw_stack(surface, stack)
        for sprite in self.dealer_cards:
            sprite.draw(surface)
        for sprites in self.hand_cards:
            for sprite in sprites:
                sprite.draw(surface)
        for stack in self.flying:
            self._draw_stack(surface, stack)
        self._draw_totals(surface)
        self._draw_labels(surface)
        if self.mode == "betting":
            self.rack.draw(surface, self.t)
        self._draw_hud(surface)
        self.draw_buttons(surface)
        self.draw_celebration(surface)
        self.draw_overlays(surface)
