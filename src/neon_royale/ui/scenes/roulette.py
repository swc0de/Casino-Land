"""Roulette table: place chips on the layout, spin, watch the ball drop, collect."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from ...core import roulette as r
from ...core.money import Cents, fmt
from ...core.roulette import Bet, RouletteTable, SpinResult, TableError
from .. import fonts, theme
from ..caches import optimise, surface_cache
from ..fx.glow import neon_frame, neon_text
from ..fx.marquee import Marquee
from ..fx.spin import WheelSpin
from ..fx.tween import ease_in_out_cubic, ease_out_back, ease_out_cubic
from ..render import wheel as wheel_art
from ..render.backdrop import felt
from ..render.chips import chip_top, draw_amount
from ..roulette_board import BoardGeometry
from ..stage import Stage
from ..theme import lerp_color
from ..widgets import ChipRack, CountingLabel, draw_panel

WHEEL_CENTER = (232, 338)
BOWL_DIAMETER = 396
FACE_DIAMETER = round(BOWL_DIAMETER * wheel_art.FACE)
BALL_RADIUS = 7
CHIP_D = 30
BALANCE_POS = (40, 672)
DEALER_POS = (WHEEL_CENTER[0] + 120, 120)
SPIN_SECONDS = 7.0
BIG_WIN_MULTIPLE = 10  # a payout of 10x the total stake gets the full celebration

NUMBER_COLORS = {
    "red": theme.ROULETTE_RED,
    "black": theme.ROULETTE_BLACK,
    "green": theme.ROULETTE_GREEN,
}


@dataclass
class Ghost:
    """A stack of chips moving around the table during a payout."""

    amount: Cents
    pos: tuple[float, float]
    alpha: float = 1.0


@surface_cache(maxsize=16)
def _highlight(size: tuple[int, int]) -> pygame.Surface:
    tile = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(tile, (255, 255, 255, 46), tile.get_rect(), border_radius=4)
    return tile


def render_board(geom: BoardGeometry) -> pygame.Surface:
    """The printed betting layout on transparent felt."""
    surf = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    line = (240, 236, 220, 210)
    num_font = fonts.get("display", 24)
    label_font = fonts.get("display", 18)

    zero = geom.zero_rect
    pygame.draw.rect(
        surf,
        (*theme.ROULETTE_GREEN, 200),
        zero,
        border_top_left_radius=30,
        border_bottom_left_radius=30,
    )
    pygame.draw.rect(surf, line, zero, 2, border_top_left_radius=30, border_bottom_left_radius=30)
    text = num_font.render("0", True, theme.WHITE)
    surf.blit(text, text.get_rect(center=zero.center))

    for n in range(1, 37):
        rect = geom.cell_rect(n)
        pygame.draw.rect(surf, line, rect, 2)
        oval = rect.inflate(-12, -22)
        pygame.draw.ellipse(surf, NUMBER_COLORS[r.color_of(n)], oval)
        pygame.draw.ellipse(surf, (255, 255, 255, 90), oval, 1)
        text = num_font.render(str(n), True, theme.WHITE)
        surf.blit(text, text.get_rect(center=(rect.centerx, rect.centery + 1)))

    for row in range(3):
        rect = geom.column_rect(row)
        pygame.draw.rect(surf, line, rect, 2)
        text = label_font.render("2:1", True, theme.WARM_WHITE)
        surf.blit(text, text.get_rect(center=rect.center))

    for i, name in enumerate(("1st 12", "2nd 12", "3rd 12")):
        rect = geom.dozen_rect(i)
        pygame.draw.rect(surf, line, rect, 2)
        text = label_font.render(name.upper(), True, theme.WARM_WHITE)
        surf.blit(text, text.get_rect(center=rect.center))

    labels = {
        r.low(): "1-18",
        r.even(): "EVEN",
        r.odd(): "ODD",
        r.high(): "19-36",
    }
    for bet, rect in geom.outside_rects():
        pygame.draw.rect(surf, line, rect, 2)
        if bet in labels:
            text = label_font.render(labels[bet], True, theme.WARM_WHITE)
            surf.blit(text, text.get_rect(center=rect.center))
        else:
            color = theme.ROULETTE_RED if bet == r.red() else theme.ROULETTE_BLACK
            cx, cy = rect.center
            diamond = [(cx, cy - 16), (cx + 30, cy), (cx, cy + 16), (cx - 30, cy)]
            pygame.draw.polygon(surf, color, diamond)
            pygame.draw.polygon(surf, line, diamond, 2)
    pygame.draw.rect(surf, (*theme.GOLD, 230), geom.rect.inflate(6, 6), 2, border_radius=6)
    return optimise(surf)


class RouletteScene(Stage):
    help_topic = "roulette"
    ambience = 0.45

    def shutdown(self) -> None:
        self.table.abandon()

    def enter(self) -> None:
        app = self.app
        self.table = RouletteTable(app.casino.wallet, app.rng)
        self.geom = BoardGeometry(left=462, top=150)
        self.spinner = WheelSpin(app.rng)

        background = felt(theme.SIZE, theme.FELT_GREEN, theme.FELT_GREEN_DARK, seed=11)
        background.blit(render_board(self.geom), (0, 0))
        self.background = background
        self.bowl = wheel_art.wheel_bowl(BOWL_DIAMETER)
        self.face = wheel_art.wheel_face(FACE_DIAMETER)
        self.ball = wheel_art.ball_sprite(BALL_RADIUS)
        self.wheel_glow = neon_frame(
            (BOWL_DIAMETER + 16, BOWL_DIAMETER + 16), theme.CYAN, 4, 999, 14
        )
        self.title = neon_text("ROULETTE", "display", 30, theme.PINK, 10)
        self.marquee = Marquee(
            pygame.Rect(10, 10, theme.WIDTH - 20, theme.HEIGHT - 20),
            spacing=34,
            radius=4,
            pattern="chase",
            speed=5,
            rng=app.rng,
        )

        board = self.geom.rect
        self.rack = ChipRack((board.centerx, 512), self.sound, diameter=54)
        self.rack.set_balance(self.table.wallet.balance)
        self.balance = CountingLabel(
            BALANCE_POS, self.table.wallet.balance, "Bankroll", "midleft", 32
        )

        y = 600
        self.btn_undo = self.button(
            (462, y, 120, 50), "UNDO", self.undo, color=theme.CYAN, hotkey=pygame.K_BACKSPACE
        )
        self.btn_clear = self.button(
            (594, y, 120, 50), "CLEAR", self.clear, color=theme.CYAN, hotkey=pygame.K_c
        )
        self.btn_double = self.button(
            (726, y, 100, 50), "2X", self.double, color=theme.PURPLE, hotkey=pygame.K_d
        )
        self.btn_rebet = self.button(
            (838, y, 130, 50), "REBET", self.rebet, color=theme.PURPLE, hotkey=pygame.K_r
        )
        self.btn_spin = self.button(
            (990, y - 6, 230, 62),
            "SPIN",
            self.spin,
            color=theme.GOLD,
            font_size=30,
            hotkey=pygame.K_SPACE,
        )
        self.button((24, 24, 130, 44), "LOBBY", self.leave, color=theme.PINK, font_size=18)
        self.add_help_button()

        self.hover_bet: Bet | None = None
        self.incoming: dict[Bet, Cents] = {}
        self.flyers: list[Ghost] = []
        self.ghosts: list[Ghost] | None = None  # replaces the live layout during payouts
        self.dolly: int | None = None
        self.dolly_t = 0.0
        self.result: SpinResult | None = None
        self.last_win: Cents = 0
        self.busy = False

    # -- actions ------------------------------------------------------------------------

    def _refresh(self) -> None:
        balance = self.table.wallet.balance
        self.balance.set(balance)
        self.rack.set_balance(balance)

    def _refuse(self, message: str) -> None:
        self.sound.play("ui_error", 0.7)
        self.toast.show(message, theme.LOSE)

    def place(self, bet: Bet) -> None:
        if self.busy:
            return
        amount = self.rack.value
        try:
            self.table.place(bet, amount)
        except TableError as exc:
            self._refuse(str(exc).capitalize())
            return
        self.dolly = None
        self._refresh()
        self._fly_chip(bet, amount)

    def _fly_chip(self, bet: Bet, amount: Cents) -> None:
        start = self.rack.rects[self.rack.selected].center
        ghost = Ghost(amount, start)
        self.flyers.append(ghost)
        self.incoming[bet] = self.incoming.get(bet, 0) + amount
        target = self.geom.spot(bet)

        def land() -> None:
            self.flyers.remove(ghost)
            self.incoming[bet] -= amount
            if self.incoming[bet] <= 0:
                del self.incoming[bet]
            self.sound.play("chip_clack", 0.8, pan=(target[0] - 640) / 640)

        self.anim.to(ghost, "pos", target, 0.22, ease_out_cubic, on_done=land)

    def remove(self, bet: Bet) -> None:
        if self.busy or bet not in self.table.bets:
            return
        self.table.remove(bet)
        self.incoming.pop(bet, None)
        self.sound.play("chip_stack", 0.6)
        self._refresh()

    def undo(self) -> None:
        if not self.busy and self.table.undo() is not None:
            self.incoming.clear()
            self.sound.play("chip_clack", 0.6)
            self._refresh()

    def clear(self) -> None:
        if not self.busy and self.table.clear():
            self.incoming.clear()
            self.sound.play("chip_stack", 0.7)
            self._refresh()

    def double(self) -> None:
        if self.busy:
            return
        if self.table.double():
            self.sound.play("chip_stack", 0.8)
            self._refresh()
        else:
            self._refuse("Can't double: check your bankroll and the table limit")

    def rebet(self) -> None:
        if self.busy:
            return
        if self.table.rebet():
            self.dolly = None
            self.sound.play("chip_stack", 0.8)
            self._refresh()
        else:
            self._refuse("Nothing to rebet, or not enough chips")

    def spin(self) -> None:
        if self.busy:
            return
        if not self.table.bets:
            self._refuse("Place your bets first")
            return
        self.busy = True
        self.incoming.clear()
        self.flyers.clear()
        self.anim.cancel_all()
        self.result = self.table.spin()
        self.dolly = None
        index = r.WHEEL_ORDER.index(self.result.number)
        self.spinner.launch(index, r.POCKETS, SPIN_SECONDS)
        self.director.run(self._spin_script(self.result))

    def leave(self) -> None:
        if self.busy:
            self._refuse("Wait for the ball to drop")
            return
        self.table.clear()
        self.sound.stop_loop("ball_roll", 200)
        self.sound.stop_loop("wheel_spin", 200)
        self.app.save()
        self.app.go("lobby")

    # -- the spin and payout sequence ----------------------------------------------------

    def _spin_script(self, result: SpinResult):
        self.toast.show("No more bets!", theme.GOLD)
        self.sound.loop("wheel_spin", 0.5, fade_ms=300)
        self.sound.loop("ball_roll", 0.9, fade_ms=100)
        while self.spinner.spinning:
            yield None
        self.sound.stop_loop("ball_roll", 250)
        self.sound.stop_loop("wheel_spin", 1500)
        yield 0.35

        number = result.number
        color = result.color
        self.dolly = number
        self.dolly_t = 0.0
        tint = {"red": theme.LOSE, "black": theme.TEXT, "green": theme.WIN}[color]
        self.banner.show(
            f"{number} {color.upper()}", "", tint, hold=1.4, center=(self.geom.rect.centerx, 120)
        )

        # Snapshot the layout as movable stacks, then settle the table.
        winners = [(p, Ghost(p.stake, self.geom.spot(p.bet))) for p in result.payouts if p.won]
        losers = [Ghost(p.stake, self.geom.spot(p.bet)) for p in result.payouts if not p.won]
        self.ghosts = [g for _, g in winners] + losers
        self.table.settle()
        self.app.casino.record_round("roulette", result.wagered, result.returned)
        yield 0.7

        if losers:
            self.sound.play("chip_stack", 0.6)
            for g in losers:
                self.anim.to(g, "pos", DEALER_POS, 0.45, ease_in_out_cubic)
                self.anim.to(g, "alpha", 0.0, 0.45)
            yield 0.5
            self.ghosts = [g for _, g in winners]

        if not winners:
            self.sound.play("lose", 0.6)
            self.toast.show("No win this time", theme.TEXT_DIM)
            self.last_win = 0
            yield from self._finish()
            return

        # Dealer pays each winning bet beside its stake.
        for payout, ghost in winners:
            paid = Ghost(payout.returned - payout.stake, DEALER_POS)
            self.ghosts.append(paid)
            target = (ghost.pos[0] + CHIP_D * 0.9, ghost.pos[1])
            self.anim.to(paid, "pos", target, 0.35, ease_out_cubic)
            self.sound.play("chip_stack", 0.7)
            self.particles.burst(target, 18, (theme.GOLD, theme.WARM_WHITE), speed=(80, 260))
            yield 0.18
        yield 0.6

        # Sweep everything won to the player.
        for g in self.ghosts:
            self.anim.to(g, "pos", BALANCE_POS, 0.5, ease_in_out_cubic)
            self.anim.to(g, "alpha", 0.0, 0.5, ease_in_out_cubic)
        big = result.returned >= result.wagered * BIG_WIN_MULTIPLE
        self.sound.play("chip_cascade" if big else "chip_stack")
        yield 0.5
        self.ghosts = None
        self.last_win = result.returned
        self._refresh()
        net = result.net
        if big:
            self.sound.play("win_big")
            self.marquee.celebrate(4.0)
            self.particles.confetti(pygame.Rect(0, 0, theme.WIDTH, 40), 160)
            self.banner.show("BIG WIN!", f"{fmt(result.returned)}", theme.GOLD, hold=2.2)
        elif net > 0:
            self.sound.play("win")
            self.marquee.celebrate(1.5)
            self.toast.show(f"You win {fmt(result.returned)}", theme.WIN)
        else:
            self.sound.play("push", 0.6)
            self.toast.show(f"Returned {fmt(result.returned)}", theme.PUSH)
        yield from self._finish()

    def _finish(self):
        self.ghosts = None
        self.busy = False
        self._refresh()
        self.app.save()
        if self.app.casino.comp_available:
            self.toast.show("Out of chips? The lobby has a gift for you.", theme.LIME)
        yield 0.0

    # -- frame --------------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.leave()
            return True
        if super().handle_event(event):
            return True
        if not self.busy and self.rack.handle_event(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            self.hover_bet = self.geom.bet_at(event.pos) if not self.busy else None
        elif event.type == pygame.MOUSEBUTTONDOWN and not self.busy:
            bet = self.geom.bet_at(event.pos)
            if bet is not None:
                if event.button == 1:
                    self.place(bet)
                elif event.button == 3:
                    self.remove(bet)
                return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        for event in self.spinner.update(dt * self.app.anim_speed):
            if event == "tick":
                self.sound.play("ball_tick", 0.8)
            elif event == "settled":
                self.sound.play("ball_drop")
        if self.spinner.flight is not None:
            self.sound.set_loop_volume("ball_roll", 0.9 * self.spinner.flight.relative_speed())
        self.dolly_t += dt
        self.marquee.update(dt)
        self.rack.update(dt)
        self.balance.update(dt)
        has_bets = bool(self.table.bets)
        idle = not self.busy
        self.btn_spin.enabled = idle and has_bets
        self.btn_undo.enabled = idle and has_bets
        self.btn_clear.enabled = idle and has_bets
        self.btn_double.enabled = idle and self.table.can_double()
        self.btn_rebet.enabled = idle and self.table.can_rebet()

    # -- drawing ------------------------------------------------------------------------

    def _draw_wheel(self, surface: pygame.Surface) -> None:
        cx, cy = WHEEL_CENTER
        self.wheel_glow.draw(surface, WHEEL_CENTER, 0.7 + 0.3 * self.spinner.spinning)
        surface.blit(self.bowl, self.bowl.get_rect(center=WHEEL_CENTER))
        face = pygame.transform.rotozoom(self.face, -math.degrees(self.spinner.wheel_angle), 1.0)
        surface.blit(face, face.get_rect(center=WHEEL_CENTER))
        if self.spinner.has_ball:
            bowl_r = BOWL_DIAMETER / 2
            height = self.spinner.ball_height()
            radius = bowl_r * (
                wheel_art.POCKET_BALL + (wheel_art.TRACK - wheel_art.POCKET_BALL) * height
            )
            bx, by = wheel_art.polar((cx, cy), radius, self.spinner.ball_angle())
            surface.blit(self.ball, self.ball.get_rect(center=(round(bx), round(by))))

    def _draw_hover(self, surface: pygame.Surface) -> None:
        bet = self.hover_bet
        if bet is None or self.busy:
            return
        rects = [self.geom.cell_rect(n) for n in bet.numbers]
        rects += [rect for b, rect in self.geom.box_bets() if b == bet]
        for rect in rects:
            tile = _highlight(rect.inflate(-4, -4).size)
            surface.blit(tile, rect.inflate(-4, -4))
        preview = chip_top(self.rack.value, CHIP_D)
        preview.set_alpha(150)
        surface.blit(preview, preview.get_rect(center=self.geom.spot(bet)))
        preview.set_alpha(255)
        staked = self.table.bets.get(bet, 0)
        info = f"{bet.label}  pays {bet.payout}:1"
        if staked:
            info += f"   on it: {fmt(staked)}"
        text = fonts.get("body_bold", 22).render(info, True, theme.WARM_WHITE)
        surface.blit(text, text.get_rect(center=(self.geom.rect.centerx, 462)))

    def _draw_bets(self, surface: pygame.Surface) -> None:
        if self.ghosts is not None:
            for g in self.ghosts:
                self._draw_ghost(surface, g)
            return
        for bet, amount in self.table.bets.items():
            shown = amount - self.incoming.get(bet, 0)
            if shown > 0:
                x, y = self.geom.spot(bet)
                draw_amount(surface, shown, (x, y + CHIP_D * 0.3), CHIP_D, per_column=8)
        for g in self.flyers:
            self._draw_ghost(surface, g)

    def _draw_ghost(self, surface: pygame.Surface, ghost: Ghost) -> None:
        if ghost.alpha >= 0.99:
            draw_amount(
                surface, ghost.amount, (ghost.pos[0], ghost.pos[1] + CHIP_D * 0.3), CHIP_D, 8
            )
            return
        if ghost.alpha <= 0.02:
            return
        layer = pygame.Surface((CHIP_D * 4, CHIP_D * 4), pygame.SRCALPHA)
        draw_amount(layer, ghost.amount, (CHIP_D * 2, CHIP_D * 3), CHIP_D, 8)
        layer.set_alpha(round(255 * ghost.alpha))
        surface.blit(layer, (ghost.pos[0] - CHIP_D * 2, ghost.pos[1] + CHIP_D * 0.3 - CHIP_D * 3))

    def _draw_dolly(self, surface: pygame.Surface) -> None:
        if self.dolly is None:
            return
        rect = self.geom.cell_rect(self.dolly)
        drop = ease_out_back(min(1.0, self.dolly_t / 0.4))
        pulse = 0.75 + 0.25 * math.sin(self.t * 6)
        frame = neon_frame(rect.inflate(6, 6).size, theme.GOLD, 3, 8, 10)
        frame.draw(surface, rect.center, pulse)
        # The dolly: a small glass marker resting on the corner of the winning number.
        cx = rect.right - 12
        cy = rect.top + 12 - 40 * (1 - drop)
        pygame.draw.circle(surface, (0, 0, 0), (cx + 2, cy + 3), 9)
        pygame.draw.circle(surface, theme.WARM_WHITE, (cx, cy), 9)
        pygame.draw.circle(surface, theme.GOLD, (cx, cy), 9, 3)
        pygame.draw.circle(surface, theme.WHITE, (cx - 3, cy - 3), 3)

    def _draw_history(self, surface: pygame.Surface) -> None:
        label = fonts.get("body_bold", 18).render("LAST", True, theme.TEXT_DIM)
        x, y = self.geom.rect.left, 112
        surface.blit(label, label.get_rect(midleft=(x, y)))
        x += label.get_width() + 18
        font = fonts.get("display", 15)
        for i, n in enumerate(self.table.history[:16]):
            color = NUMBER_COLORS[r.color_of(n)]
            radius = 15 if i == 0 else 13
            pygame.draw.circle(surface, color, (x, y), radius)
            pygame.draw.circle(
                surface, theme.GOLD if i == 0 else (220, 220, 220), (x, y), radius, 2
            )
            text = font.render(str(n), True, theme.WHITE)
            surface.blit(text, text.get_rect(center=(x, y + 1)))
            x += radius * 2 + 6

    def _draw_hud(self, surface: pygame.Surface) -> None:
        self.title.draw(surface, (WHEEL_CENTER[0] + 92, 46))
        panel = pygame.Rect(22, 590, 400, 116)
        draw_panel(surface, panel, (8, 4, 20, 190), theme.PURPLE, 14)
        self.balance.draw(surface)
        small = fonts.get("body_bold", 20)
        bet_text = small.render(f"ON TABLE  {fmt(self.table.total_bet)}", True, theme.TEXT)
        surface.blit(bet_text, (240, 606))
        last = small.render(
            f"LAST WIN  {fmt(self.last_win)}", True, theme.WIN if self.last_win else theme.TEXT_DIM
        )
        surface.blit(last, (240, 636))
        limits = fonts.get("body", 17).render(
            f"Table {fmt(r.MIN_BET)} - {fmt(r.MAX_TABLE)}  ·  European single zero",
            True,
            theme.TEXT_MUTED,
        )
        surface.blit(limits, (240, 668))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        self.marquee.draw(surface)
        self._draw_wheel(surface)
        self._draw_history(surface)
        self._draw_dolly(surface)
        self._draw_hover(surface)
        self._draw_bets(surface)
        self.rack.draw(surface, self.t)
        self._draw_hud(surface)
        self.draw_buttons(surface)
        self.draw_overlays(surface)
        if self.busy and self.spinner.spinning:
            glow = lerp_color(theme.GOLD, theme.WHITE, 0.3)
            text = fonts.get("display", 22).render("NO MORE BETS", True, glow)
            surface.blit(text, text.get_rect(center=(self.geom.rect.centerx, 462)))
