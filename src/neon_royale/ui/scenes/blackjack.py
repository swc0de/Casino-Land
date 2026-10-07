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
from ..fx.glow import NeonGraphic, neon_text
from ..fx.marquee import Marquee
from ..fx.tween import ease_in_out_cubic, ease_out_back, ease_out_cubic
from ..render.backdrop import felt
from ..render.cards import card_back
from ..render.chips import draw_amount
from ..sprites import CardSprite
from ..stage import Stage
from ..theme import Color
from ..widgets import ChipRack, CountingLabel, draw_panel

CARD_W = 92
SHOE_POS = (1118, 128)
DISCARD_POS = (150, 128)
DEALER_Y = 165
HAND_Y = 425
BET_Y = 566
ARC_CENTER = (640, -420)
BANNER_AT = (640, 262)
ARC_RADIUS = 690
BALANCE_POS = (40, 672)
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


def render_table() -> pygame.Surface:
    surf = felt(theme.SIZE, theme.FELT_BLUE, theme.FELT_BLUE_DARK, seed=21)
    print_color = (220, 230, 255)
    mask = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255), ARC_CENTER, ARC_RADIUS, 4)
    arc = NeonGraphic(mask, theme.CYAN, 12)
    arc.halo.set_alpha(190)
    surf.blit(arc.halo, (-arc.margin, -arc.margin))
    surf.blit(arc.core, (-arc.margin, -arc.margin))
    _arc_text(
        surf,
        "BLACKJACK PAYS 3 TO 2",
        ARC_CENTER,
        ARC_RADIUS + 34,
        fonts.get("display", 28),
        theme.GOLD,
        1.06,
    )
    _arc_text(
        surf,
        "DEALER MUST STAND ON ALL 17s  ·  INSURANCE PAYS 2 TO 1",
        ARC_CENTER,
        ARC_RADIUS + 80,
        fonts.get("body_bold", 22),
        print_color,
        1.04,
    )
    # Shoe and discard tray.
    shoe = pygame.Rect(0, 0, 120, 150)
    shoe.center = SHOE_POS
    pygame.draw.rect(surf, (20, 12, 30), shoe.inflate(10, 10), border_radius=14)
    pygame.draw.rect(surf, theme.BRASS, shoe.inflate(10, 10), 3, border_radius=14)
    back = card_back(CARD_W)
    for i in range(4):
        surf.blit(back, back.get_rect(center=(SHOE_POS[0] - 6 + i * 3, SHOE_POS[1] - i * 2)))
    tray = pygame.Rect(0, 0, 120, 150)
    tray.center = DISCARD_POS
    pygame.draw.rect(surf, (10, 22, 50), tray, border_radius=12)
    pygame.draw.rect(surf, (90, 120, 180), tray, 2, border_radius=12)
    return optimise(surf)


class BlackjackScene(Stage):
    def enter(self) -> None:
        app = self.app
        self.table = BlackjackTable(app.casino.wallet, app.rng)
        self.background = render_table()
        self.title = neon_text("BLACKJACK", "display", 30, theme.CYAN, 10)
        self.marquee = Marquee(
            pygame.Rect(10, 10, theme.WIDTH - 20, theme.HEIGHT - 20),
            spacing=34,
            radius=4,
            pattern="chase",
            speed=5,
            rng=app.rng,
        )
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
        self.btn_clear = b(
            (870, y, 120, 52), "CLEAR", self.clear_bet, color=theme.CYAN, hotkey=pygame.K_c
        )
        self.btn_deal = b(
            (1006, y - 6, 220, 64),
            "DEAL",
            self.deal,
            color=theme.GOLD,
            font_size=30,
            hotkey=pygame.K_SPACE,
        )
        # Player decisions.
        actions = (
            ("HIT", Action.HIT, pygame.K_h, theme.LIME),
            ("STAND", Action.STAND, pygame.K_s, theme.PINK),
            ("DOUBLE", Action.DOUBLE, pygame.K_d, theme.GOLD),
            ("SPLIT", Action.SPLIT, pygame.K_p, theme.CYAN),
            ("SURRENDER", Action.SURRENDER, pygame.K_r, theme.PURPLE),
        )
        self.action_buttons: dict[Action, object] = {}
        x = 330
        for label, action, key, color in actions:
            width = 168 if action is Action.SURRENDER else 132
            self.action_buttons[action] = b(
                (x, y, width, 54),
                label,
                lambda a=action: self.act(a),
                color=color,
                hotkey=key,
                font_size=21,
            )
            x += width + 12
        self.btn_hint = b(
            (x, y, 110, 54),
            "HINT",
            self.hint,
            color=theme.TEXT_DIM,
            hotkey=pygame.K_QUESTION,
            font_size=20,
        )
        # Insurance.
        self.btn_insure = b(
            (430, y, 250, 54),
            "INSURANCE",
            self.insure,
            color=theme.GOLD,
            hotkey=pygame.K_i,
            font_size=22,
        )
        self.btn_no_insure = b(
            (700, y, 250, 54),
            "NO THANKS",
            self.no_insurance,
            color=theme.PINK,
            hotkey=pygame.K_n,
            font_size=22,
        )
        self.button((24, 24, 130, 44), "LOBBY", self.leave, color=theme.PINK, font_size=18)

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
        self.toast.show(f"Basic strategy says: {best.value.upper()}", theme.CYAN)

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
                self.toast.show("Shuffling a fresh shoe…", theme.CYAN)
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
            self.marquee.celebrate(3.0)
            self.particles.confetti(pygame.Rect(0, 0, theme.WIDTH, 40), 110)
            self.banner.show("BLACKJACK!", "", theme.GOLD, hold=1.6, center=BANNER_AT)
        elif event.net >= self.table.last_bet * 4 and event.net > 0:
            self.sound.play("win_big")
            self.marquee.celebrate(3.5)
            self.particles.confetti(pygame.Rect(0, 0, theme.WIDTH, 40), 140)
            self.banner.show("BIG WIN!", "", theme.GOLD, hold=1.8, center=BANNER_AT)
        elif event.net > 0:
            self.sound.play("win")
            self.marquee.celebrate(1.2)
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
            self.toast.show("Out of chips? The lobby has a gift for you.", theme.LIME)

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
        self.marquee.update(dt)
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
            ring = neon_text("BET", "display", 18, theme.GOLD, 6)
            if not self.bet_chips:
                ring.draw(surface, (640, BET_Y), pulse)
            else:
                draw_amount(surface, self.pending_bet, (640, BET_Y + 18), 40)
                amount = fonts.get("display", 22).render(fmt(self.pending_bet), True, theme.WHITE)
                surface.blit(amount, amount.get_rect(midleft=(700, BET_Y)))
            return
        for i in range(len(self.stacks)):
            x = self.hand_x(i)
            pygame.draw.circle(surface, theme.GOLD, (round(x), BET_Y), 40, 2)
            if i == self.table.active and self.mode == "player" and len(self.stacks) > 1:
                bob = 4 * math.sin(self.t * 6)
                tip = (x, BET_Y + 48 + bob)
                points = [tip, (tip[0] - 12, tip[1] + 16), (tip[0] + 12, tip[1] + 16)]
                pygame.draw.polygon(surface, theme.CYAN, points)

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
        font = fonts.get("display", 20)
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
        box = label.get_rect(center=center).inflate(22, 10)
        draw_panel(surface, box, (8, 6, 24, 220), theme.CYAN if glow else (90, 90, 140), 10)
        surface.blit(label, label.get_rect(center=box.center))

    def _draw_labels(self, surface: pygame.Surface) -> None:
        for i, (text, color, age) in self.labels.items():
            pop = ease_out_back(min(1.0, age / 0.3))
            graphic = neon_text(text, "display", 26, color, 10)
            y = HAND_Y - 112 - 10 * (1 - pop)
            w, h = graphic.content_size
            pill = pygame.Rect(0, 0, w + 28, h + 6)
            pill.center = (round(self.hand_x(i)), round(y))
            draw_panel(surface, pill, (6, 6, 20, round(200 * min(1.0, age / 0.2))), None, 16)
            graphic.draw(surface, (self.hand_x(i), y), min(1.0, age / 0.2))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        self.title.draw(surface, (640, 40))
        panel = pygame.Rect(22, 604, 286, 102)
        draw_panel(surface, panel, (8, 4, 20, 190), theme.PURPLE, 14)
        self.balance.draw(surface)
        info = fonts.get("body", 17).render(
            f"Bets {fmt(self.table.min_bet)} - {fmt(self.table.max_bet)}  ·  6 decks",
            True,
            theme.TEXT_MUTED,
        )
        surface.blit(info, info.get_rect(center=(640, 72)))
        left = self.table.shoe.remaining
        shoe = fonts.get("body_bold", 17).render(f"{left} cards in shoe", True, theme.TEXT_DIM)
        surface.blit(shoe, shoe.get_rect(center=(SHOE_POS[0], SHOE_POS[1] + 92)))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        self.marquee.draw(surface)
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
        self.draw_overlays(surface)
