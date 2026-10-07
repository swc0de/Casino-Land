"""The casino floor: three neon-lit game cabinets under the marquee."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from ...core.cards import Card, Rank, Suit
from ...core.money import dollars, fmt
from .. import fonts, theme
from ..caches import optimise
from ..fx.glow import neon_frame, neon_text
from ..fx.marquee import Marquee
from ..fx.signboard import SignBoard
from ..render.backdrop import casino_night
from ..render.cards import card_face
from ..render.chips import chip_top, draw_amount
from ..stage import Stage
from ..theme import Color, lerp_color, scale_color
from ..widgets import CountingLabel, draw_panel
from . import REGISTRY

HORIZON = 300
CABINET_SIZE = (330, 390)


# -- cabinet illustrations ------------------------------------------------------------


def _mini_wheel(surface: pygame.Surface, center: tuple[int, int], radius: int) -> None:
    ss = 2
    size = radius * 2 * ss
    wheel = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (size / 2, size / 2)
    r = size / 2
    pygame.draw.circle(wheel, (70, 34, 14), c, r)
    pygame.draw.circle(wheel, theme.BRASS, c, r, ss * 2)
    pockets = 37
    for i in range(pockets):
        a0 = i / pockets * math.tau - math.pi / 2
        a1 = (i + 1) / pockets * math.tau - math.pi / 2
        color = (
            theme.ROULETTE_GREEN
            if i == 0
            else (theme.ROULETTE_RED if i % 2 else theme.ROULETTE_BLACK)
        )
        pts = [c]
        for k in range(5):
            a = a0 + (a1 - a0) * k / 4
            pts.append((c[0] + math.cos(a) * r * 0.86, c[1] + math.sin(a) * r * 0.86))
        pygame.draw.polygon(wheel, color, pts)
    pygame.draw.circle(wheel, (52, 26, 12), c, r * 0.58)
    pygame.draw.circle(wheel, theme.BRASS, c, r * 0.58, ss)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        end = (c[0] + math.cos(a) * r * 0.42, c[1] + math.sin(a) * r * 0.42)
        pygame.draw.line(wheel, theme.GOLD, c, end, ss * 3)
    pygame.draw.circle(wheel, theme.GOLD, c, r * 0.12)
    pygame.draw.circle(wheel, theme.WHITE, (c[0] + r * 0.74, c[1] - r * 0.28), r * 0.06)
    wheel = pygame.transform.smoothscale(wheel, (radius * 2, radius * 2))
    surface.blit(wheel, wheel.get_rect(center=center))


def _fan(
    surface: pygame.Surface,
    cards: list[Card],
    center: tuple[int, int],
    width: int,
    spread: float,
    step: int,
) -> None:
    n = len(cards)
    for i, card in enumerate(cards):
        angle = spread * ((n - 1) / 2 - i)
        face = pygame.transform.rotozoom(card_face(card, width), angle, 1.0)
        x = center[0] + (i - (n - 1) / 2) * step
        y = center[1] + abs(i - (n - 1) / 2) * 6
        surface.blit(face, face.get_rect(center=(x, y)))


def _draw_roulette_art(surface: pygame.Surface, area: pygame.Rect) -> None:
    _mini_wheel(surface, area.center, 92)


def _draw_blackjack_art(surface: pygame.Surface, area: pygame.Rect) -> None:
    cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)]
    _fan(surface, cards, (area.centerx, area.centery - 10), 96, 12, 46)
    draw_amount(surface, dollars(150), (area.centerx + 92, area.bottom - 4), 40)


def _draw_poker_art(surface: pygame.Surface, area: pygame.Rect) -> None:
    hand = [Card(Rank(r), Suit.HEARTS) for r in (10, 11, 12, 13, 14)]
    _fan(surface, hand, (area.centerx, area.centery - 8), 74, 9, 30)
    draw_amount(surface, dollars(560), (area.centerx - 104, area.bottom - 2), 36)


@dataclass
class GameInfo:
    key: str
    title: str
    color: Color
    lines: tuple[str, ...]
    art: Callable[[pygame.Surface, pygame.Rect], None]


GAMES = (
    GameInfo(
        "roulette",
        "ROULETTE",
        theme.PINK,
        ("European single zero", "Table limits $1 - $5,000"),
        _draw_roulette_art,
    ),
    GameInfo(
        "blackjack",
        "BLACKJACK",
        theme.CYAN,
        ("Blackjack pays 3:2", "Dealer stands on soft 17", "Bets $5 - $5,000"),
        _draw_blackjack_art,
    ),
    GameInfo(
        "poker",
        "HOLD'EM",
        theme.GOLD,
        ("No-Limit Texas Hold'em", "6 seats, blinds $5/$10"),
        _draw_poker_art,
    ),
)


class Cabinet:
    def __init__(self, info: GameInfo, rect: pygame.Rect, rng) -> None:
        self.info = info
        self.rect = rect
        self.hover_t = 0.0
        self.hovered = False
        self.marquee = Marquee(
            rect.inflate(-14, -14),
            spacing=22,
            radius=3,
            pattern="wave",
            speed=3,
            rng=rng,
            color=lerp_color(info.color, theme.WHITE, 0.5),
        )
        self.body = self._render_body()
        self.title = neon_text(info.title, "display", 34, info.color, 12)
        self.frame = neon_frame(rect.size, info.color, width=4, corner=24, radius=12)

    def _render_body(self) -> pygame.Surface:
        w, h = self.rect.size
        body = pygame.Surface((w, h), pygame.SRCALPHA)
        top = scale_color(self.info.color, 0.16)
        for y in range(h):
            k = y / h
            color = lerp_color(top, (10, 6, 22), k**0.7)
            pygame.draw.line(body, (*color, 238), (0, y), (w, y))
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=24)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.info.art(body, pygame.Rect(20, 84, w - 40, 176))
        for i, line in enumerate(self.info.lines):
            text = fonts.get("body_bold", 21).render(line, True, theme.TEXT)
            body.blit(text, text.get_rect(center=(w / 2, 288 + i * 24)))
        return optimise(body)

    @property
    def lift(self) -> float:
        return -8 * self.hover_t

    def update(self, dt: float) -> None:
        target = 1.0 if self.hovered else 0.0
        self.hover_t += (target - self.hover_t) * min(1.0, dt * 10)
        self.marquee.pattern = "chase" if self.hovered else "wave"
        self.marquee.speed = 9 if self.hovered else 3
        self.marquee.update(dt)

    def draw(self, surface: pygame.Surface, open_: bool) -> None:
        rect = self.rect.move(0, round(self.lift))
        surface.blit(self.body, rect)
        self.marquee.draw(surface, offset=(0, round(self.lift)))
        intensity = 0.7 + 0.3 * self.hover_t
        self.frame.draw(surface, rect.center, intensity, halo_strength=0.6 + 0.4 * self.hover_t)
        self.title.draw(surface, (rect.centerx, rect.top + 50), 0.85 + 0.15 * self.hover_t)
        hint = "PLAY" if open_ else "OPENING SOON"
        label = fonts.get("display", 20).render(
            hint, True, theme.WHITE if open_ else theme.TEXT_DIM
        )
        label.set_alpha(round(120 + 135 * self.hover_t))
        surface.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 24)))


class LobbyScene(Stage):
    def enter(self) -> None:
        self.backdrop = casino_night(HORIZON)
        self.sign = SignBoard(
            pygame.Rect(300, 14, 680, 126),
            "NEON ROYALE",
            self.app.rng,
            title_size=58,
            bulb_radius=4,
            dying_letter=7,
        )
        self.sign.skip_intro()
        w, h = CABINET_SIZE
        gap = 46
        left = (theme.WIDTH - (3 * w + 2 * gap)) // 2
        self.cabinets = [
            Cabinet(info, pygame.Rect(left + i * (w + gap), 168, w, h), self.app.rng)
            for i, info in enumerate(GAMES)
        ]
        casino = self.app.casino
        self.balance = CountingLabel((48, 668), casino.balance, "Bankroll", "midleft", 34)
        self.comp_button = self.button(
            (330, 636, 330, 52),
            f"CLAIM FREE {fmt(dollars(1_000))}",
            self._claim_comp,
            color=theme.LIME,
            font_size=20,
        )
        self.button(
            (704, 640, 136, 48),
            "STATS",
            self._overlay("stats"),
            color=theme.GOLD,
            hotkey=pygame.K_s,
            font_size=20,
        )
        self.button(
            (852, 640, 186, 48),
            "SETTINGS",
            self._overlay("settings"),
            color=theme.CYAN,
            hotkey=pygame.K_o,
            font_size=20,
        )
        self.button(
            (theme.WIDTH - 230, 640, 186, 48),
            "EXIT",
            self.app.quit,
            color=theme.PURPLE,
            font_size=20,
        )
        self.ambient_timer = 0.0

    def _overlay(self, name: str):
        def push() -> None:
            self.app.scenes.push(self.app.make_scene(name))

        return push

    def _claim_comp(self) -> None:
        amount = self.app.casino.claim_comp()
        if amount:
            self.sound.play("chip_cascade")
            self.sound.play("win")
            self.toast.show(f"The house sends over {fmt(amount)} in chips. Good luck!", theme.LIME)
            chips = [chip_top(d, 34) for d in (dollars(25), dollars(100), dollars(500))]
            self.particles.sprite_fountain((theme.WIDTH // 2, 640), chips, 24)
            self.particles.burst((theme.WIDTH // 2, 640), 60, (theme.LIME, theme.GOLD))
            self.app.save()

    def _open(self, cabinet: Cabinet) -> None:
        if cabinet.info.key in REGISTRY:
            self.sound.play("ui_click")
            self.app.go(cabinet.info.key)
        else:
            self.sound.play("ui_error", 0.6)
            self.toast.show(f"{cabinet.info.title.title()} opens in the next update", theme.GOLD)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if super().handle_event(event):
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.go("title")
            return True
        if event.type == pygame.MOUSEMOTION:
            for cabinet in self.cabinets:
                inside = cabinet.rect.collidepoint(event.pos)
                if inside and not cabinet.hovered:
                    self.sound.play("ui_hover", 0.7)
                cabinet.hovered = inside
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for cabinet in self.cabinets:
                if cabinet.rect.collidepoint(event.pos):
                    self._open(cabinet)
                    return True
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self._open(self.cabinets[event.key - pygame.K_1])
            return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        self.sign.update(dt)
        for cabinet in self.cabinets:
            cabinet.update(dt)
        self.balance.set(self.app.casino.balance)
        self.balance.update(dt)
        self.comp_button.visible = self.app.casino.comp_available
        # Lazy sparkles drifting up from the floor.
        self.ambient_timer -= dt
        if self.ambient_timer <= 0:
            self.ambient_timer = 0.12
            x = self.app.rng.uniform(0, theme.WIDTH)
            self.particles.burst(
                (x, theme.HEIGHT),
                count=1,
                colors=(theme.PINK, theme.CYAN, theme.PURPLE),
                speed=(30, 80),
                direction=-math.pi / 2,
                spread=0.6,
                gravity=-10,
                drag=0.1,
                life=(3.0, 5.0),
                size=(1, 3),
            )

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.backdrop, (0, 0))
        self.particles.draw(surface)
        self.sign.draw(surface)
        for cabinet in self.cabinets:
            cabinet.draw(surface, cabinet.info.key in REGISTRY)
        bar = pygame.Rect(0, 612, theme.WIDTH, theme.HEIGHT - 612)
        draw_panel(surface, bar.inflate(-24, -12), (8, 4, 20, 200), theme.PURPLE, 16)
        self.balance.draw(surface)
        self.draw_buttons(surface)
        self.banner.draw(surface)
        self.toast.draw(surface)
