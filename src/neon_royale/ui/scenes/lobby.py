"""The casino floor seen from above: three tables under pendant lights on ornate carpet."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from ...core.cards import Card, Rank, Suit
from ...core.money import dollars, fmt
from ...core.roulette import color_of
from .. import fonts, theme
from ..caches import optimise, surface_cache
from ..render import wheel as wheel_art
from ..render.backdrop import felt
from ..render.cards import card_back, card_face
from ..render.chips import chip_top, draw_amount
from ..render.decor import (
    brass_plaque,
    carpet,
    crown,
    draw_gilded_frame,
    engraved_text,
    lacquer_panel,
    light_pool,
    padded_band,
    padded_ellipse,
    scatter_sparkles,
    wood,
)
from ..stage import Stage
from ..theme import lerp_color
from ..widgets import CountingLabel
from . import REGISTRY

TABLE_SIZE = (360, 260)
TABLE_Y = 318
HEADER_H = 84
FOOTER_Y = 618
S = 2  # supersampling for the table miniatures


# -- furniture ------------------------------------------------------------------------


def _chair(surface: pygame.Surface, center: tuple[float, float], facing: float, r: float) -> None:
    """A leather casino chair seen from above; ``facing`` points at the table (radians)."""
    cx, cy = center
    back = (cx - math.cos(facing) * r * 0.75, cy - math.sin(facing) * r * 0.75)
    pygame.draw.circle(surface, (0, 0, 0, 90), (cx + r * 0.15, cy + r * 0.25), r * 1.05)
    pygame.draw.circle(surface, (40, 16, 12), back, r * 0.8)
    pygame.draw.circle(surface, (22, 14, 12), (cx, cy), r)
    pygame.draw.circle(surface, (70, 30, 24), (cx, cy), r * 0.82)
    pygame.draw.circle(surface, (110, 52, 40), (cx - r * 0.25, cy - r * 0.25), r * 0.35)
    pygame.draw.circle(surface, theme.BRASS, (cx, cy), r, max(1, round(r * 0.08)))


def _clip_shape(surface: pygame.Surface, mask: pygame.Surface) -> pygame.Surface:
    out = surface.copy()
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


def _felt_in(size: tuple[int, int], mask: pygame.Surface, seed: int) -> pygame.Surface:
    cloth = felt(size, theme.FELT_GREEN, theme.FELT_GREEN_DARK, seed).convert_alpha()
    return _clip_shape(cloth, mask)


def _roulette_table() -> pygame.Surface:
    w, h = TABLE_SIZE[0] * S, TABLE_SIZE[1] * S
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    table = pygame.Rect(0, 0, 300 * S, 172 * S)
    table.center = (w // 2, h // 2 - 12 * S)
    for x in range(table.left + 40 * S, table.right - 20 * S, 52 * S):
        _chair(surf, (x, table.bottom + 26 * S), -math.pi / 2, 17 * S)
    _chair(surf, (table.right - 70 * S, table.top - 22 * S), math.pi / 2, 16 * S)
    rail = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(rail, (255, 255, 255), table, border_radius=40 * S)
    surf.blit(_clip_shape(wood((w, h), theme.MAHOGANY, 9).convert_alpha(), rail), (0, 0))
    inner = table.inflate(-24 * S, -24 * S)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255), inner, border_radius=30 * S)
    surf.blit(_felt_in((w, h), mask, 3), (0, 0))
    pygame.draw.rect(surf, theme.GOLD, inner, S * 2, border_radius=30 * S)
    # The wheel at one end.
    wc = (inner.left + 62 * S, inner.centery)
    bowl = wheel_art.wheel_bowl(112 * S)
    face = wheel_art.wheel_face(round(112 * S * wheel_art.FACE))
    surf.blit(bowl, bowl.get_rect(center=wc))
    surf.blit(face, face.get_rect(center=wc))
    # The betting layout.
    cell_w, cell_h = 12 * S, 22 * S
    gx, gy = inner.left + 136 * S, inner.centery - cell_h * 1.5
    line = (236, 226, 196)
    zero = pygame.Rect(gx - cell_w, gy, cell_w, cell_h * 3)
    pygame.draw.rect(surf, theme.ROULETTE_GREEN, zero)
    for n in range(1, 37):
        street, row = (n - 1) // 3, (n - 1) % 3
        cell = pygame.Rect(gx + street * cell_w, gy + (2 - row) * cell_h, cell_w, cell_h)
        color = theme.ROULETTE_RED if color_of(n) == "red" else theme.ROULETTE_BLACK
        pygame.draw.rect(surf, color, cell.inflate(-3 * S, -6 * S), border_radius=2 * S)
        pygame.draw.rect(surf, line, cell, 1 * S)
    pygame.draw.rect(surf, line, zero, 1 * S)
    for i in range(3):
        pygame.draw.rect(surf, line, (gx + i * 4 * cell_w, gy + 3 * cell_h, 4 * cell_w, 14 * S), S)
    for x, y, d in (
        (gx + 5 * cell_w, gy + cell_h, dollars(25)),
        (gx + 9 * cell_w, gy, dollars(100)),
        (gx + 2 * cell_w, gy + 2 * cell_h, dollars(5)),
    ):
        chip = chip_top(d, 13 * S)
        surf.blit(chip, chip.get_rect(center=(x + cell_w // 2, y + cell_h // 2)))
    return pygame.transform.smoothscale(surf, TABLE_SIZE)


def _blackjack_table() -> pygame.Surface:
    w, h = TABLE_SIZE[0] * S, TABLE_SIZE[1] * S
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, top = w // 2, 34 * S
    oval = pygame.Rect(0, 0, 316 * S, 380 * S)
    oval.midtop = (cx, top - 190 * S)
    # Chairs round the curve.
    for i in range(5):
        a = math.radians(30 + i * 30)
        x = cx + math.cos(a) * 176 * S
        y = oval.centery + math.sin(a) * 214 * S
        _chair(surf, (x, y), a + math.pi, 17 * S)
    half = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(half, (255, 255, 255), oval)
    pygame.draw.rect(half, (0, 0, 0, 0), (0, 0, w, top))
    rail_layer = pygame.Surface((w, h), pygame.SRCALPHA)
    padded_ellipse(rail_layer, oval, 22 * S)
    pygame.draw.rect(rail_layer, (0, 0, 0, 0), (0, 0, w, top))
    inner = oval.inflate(-40 * S, -40 * S)
    felt_mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(felt_mask, (255, 255, 255), inner)
    pygame.draw.rect(felt_mask, (0, 0, 0, 0), (0, 0, w, top))
    surf.blit(_felt_in((w, h), felt_mask, 5), (0, 0))
    surf.blit(rail_layer, (0, 0))
    # Dealer's edge with the chip tray.
    edge = pygame.Rect(oval.left + 6 * S, top - 12 * S, oval.width - 12 * S, 14 * S)
    surf.blit(wood(edge.size, theme.MAHOGANY, 2), edge)
    tray = pygame.Rect(0, 0, 150 * S, 26 * S)
    tray.midtop = (cx, top + 2 * S)
    pygame.draw.rect(surf, (30, 16, 10), tray, border_radius=4 * S)
    colors = ((236, 236, 240), (206, 30, 44), (20, 140, 74), (30, 30, 38), (114, 46, 182))
    for i in range(10):
        x = tray.left + 6 * S + i * 14 * S
        pygame.draw.rect(
            surf, colors[i % 5], (x, tray.top + 4 * S, 11 * S, 18 * S), border_radius=3 * S
        )
    # Printed arcs and betting circles.
    arc = inner.inflate(-60 * S, -60 * S)
    pygame.draw.arc(surf, theme.GOLD, arc, math.radians(200), math.radians(340), S * 2)
    for i in range(5):
        a = math.radians(30 + i * 30)
        x = cx + math.cos(a) * 112 * S
        y = oval.centery + math.sin(a) * 150 * S
        pygame.draw.circle(surf, (236, 226, 196), (x, y), 13 * S, S * 2)
    # A hand in progress.
    for i, card in enumerate((Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS))):
        face = card_face(card, 30 * S)
        surf.blit(face, face.get_rect(center=(cx - 10 * S + i * 18 * S, top + 66 * S)))
    back = card_back(30 * S)
    surf.blit(back, back.get_rect(center=(cx + 40 * S, top + 66 * S)))
    for i, card in enumerate((Card(Rank.TEN, Suit.CLUBS), Card(Rank.NINE, Suit.DIAMONDS))):
        face = card_face(card, 26 * S)
        surf.blit(face, face.get_rect(center=(cx - 8 * S + i * 14 * S, top + 140 * S)))
    return pygame.transform.smoothscale(surf, TABLE_SIZE)


def _poker_table() -> pygame.Surface:
    w, h = TABLE_SIZE[0] * S, TABLE_SIZE[1] * S
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    oval = pygame.Rect(0, 0, 300 * S, 176 * S)
    oval.center = (w // 2, h // 2)
    for i in range(6):
        a = math.radians(90 + i * 60)
        x = oval.centerx + math.cos(a) * 168 * S
        y = oval.centery + math.sin(a) * 108 * S
        _chair(surf, (x, y), a + math.pi, 17 * S)
    padded_ellipse(surf, oval, 22 * S)
    race = oval.inflate(-42 * S, -42 * S)
    race_mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(race_mask, (255, 255, 255), race)
    surf.blit(_clip_shape(wood((w, h), theme.WALNUT, 6).convert_alpha(), race_mask), (0, 0))
    inner = race.inflate(-16 * S, -16 * S)
    felt_mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(felt_mask, (255, 255, 255), inner)
    surf.blit(_felt_in((w, h), felt_mask, 8), (0, 0))
    pygame.draw.ellipse(surf, theme.GOLD, inner.inflate(-30 * S, -30 * S), S)
    board = [
        Card(Rank(r), s)
        for r, s in (
            (14, Suit.HEARTS),
            (13, Suit.HEARTS),
            (7, Suit.CLUBS),
            (12, Suit.HEARTS),
            (11, Suit.HEARTS),
        )
    ]
    for i, card in enumerate(board):
        face = card_face(card, 24 * S)
        surf.blit(face, face.get_rect(center=(oval.centerx + (i - 2) * 28 * S, oval.centery)))
    for x, y, amount in ((-70, -40, dollars(240)), (60, 40, dollars(75)), (-40, 44, dollars(30))):
        draw_amount(surf, amount, (oval.centerx + x * S, oval.centery + y * S), 16 * S)
    return pygame.transform.smoothscale(surf, TABLE_SIZE)


@surface_cache(maxsize=4)
def table_image(key: str) -> pygame.Surface:
    return optimise(
        {"roulette": _roulette_table, "blackjack": _blackjack_table, "poker": _poker_table}[key]()
    )


@surface_cache(maxsize=2)
def floor() -> pygame.Surface:
    """Carpet with the wood header and footer bars."""
    surf = carpet(theme.SIZE, dim=0.8).copy()
    top = wood((theme.WIDTH, HEADER_H), theme.WALNUT, 11)
    surf.blit(top, (0, 0))
    padded_band(surf, pygame.Rect(0, HEADER_H - 10, theme.WIDTH, 10), (40, 26, 10), theme.GOLD)
    bottom = wood((theme.WIDTH, theme.HEIGHT - FOOTER_Y), theme.WALNUT, 12)
    surf.blit(bottom, (0, FOOTER_Y))
    padded_band(surf, pygame.Rect(0, FOOTER_Y, theme.WIDTH, 8), (40, 26, 10), theme.GOLD)
    shade = pygame.Surface((theme.WIDTH, 30), pygame.SRCALPHA)
    for y in range(30):
        pygame.draw.line(shade, (0, 0, 0, round(120 * (1 - y / 30))), (0, y), (theme.WIDTH, y))
    surf.blit(shade, (0, HEADER_H))
    return surf


# -- the floor ------------------------------------------------------------------------


@dataclass
class GameInfo:
    key: str
    title: str
    lines: tuple[str, ...]


GAMES = (
    GameInfo("roulette", "ROULETTE", ("European single zero", "$1 minimum · $5,000 limit")),
    GameInfo("blackjack", "BLACKJACK", ("Blackjack pays 3:2", "Dealer stands on soft 17")),
    GameInfo("poker", "HOLD'EM POKER", ("No-limit · six seats", "Blinds $5 / $10")),
)


class TableSpot:
    def __init__(self, info: GameInfo, center: tuple[int, int]) -> None:
        self.info = info
        self.center = center
        self.image = table_image(info.key)
        self.rect = self.image.get_rect(center=center).inflate(-10, 40).move(0, 22)
        self.plaque = brass_plaque((250, 46), info.title, 22)
        self.pool = light_pool((520, 380), (255, 214, 150), 110)
        self.hover_pool = light_pool((520, 380), (255, 226, 170), 90)
        self.hover_t = 0.0
        self.hovered = False

    def update(self, dt: float) -> None:
        target = 1.0 if self.hovered else 0.0
        self.hover_t += (target - self.hover_t) * min(1.0, dt * 9)

    def draw(self, surface: pygame.Surface, t: float, open_: bool) -> None:
        cx, cy = self.center
        surface.blit(self.pool, self.pool.get_rect(center=(cx, cy + 10)))
        if self.hover_t > 0.02:
            self.hover_pool.set_alpha(round(255 * self.hover_t))
            surface.blit(self.hover_pool, self.hover_pool.get_rect(center=(cx, cy + 10)))
        surface.blit(self.image, self.image.get_rect(center=(cx, cy)))
        plaque_rect = self.plaque.get_rect(center=(cx, cy + 162))
        if self.hover_t > 0.05:
            draw_gilded_frame(surface, plaque_rect.inflate(10, 10), 2, 12, round(self.hover_t, 1))
        surface.blit(self.plaque, plaque_rect)
        font = fonts.get("body", 17)
        backing = pygame.Rect(0, 0, 260, 48)
        backing.midtop = (cx, cy + 190)
        lacquer_panel(surface, backing, (14, 8, 6), 200, False, 10)
        for i, line in enumerate(self.info.lines):
            text = font.render(line, True, lerp_color(theme.TEXT_DIM, theme.TEXT, self.hover_t))
            surface.blit(text, text.get_rect(center=(cx, cy + 202 + i * 21)))
        if self.hover_t > 0.05:
            hint = engraved_text(
                "TAKE A SEAT" if open_ else "OPENING SOON",
                "display",
                22,
                "gold" if open_ else "cream",
            )
            hint.draw(surface, (cx, cy - 150), self.hover_t)
            scatter_sparkles(surface, self.image.get_rect(center=(cx, cy)), t, 5, seed=cx)


class LobbyScene(Stage):
    def enter(self) -> None:
        self.background = floor()
        self.logo = engraved_text("NEON ROYALE", "logo", 44, "gold", glow=0.35)
        xs = (232, 640, 1048)
        self.tables = [TableSpot(info, (x, TABLE_Y)) for info, x in zip(GAMES, xs, strict=True)]
        casino = self.app.casino
        self.balance = CountingLabel((52, 676), casino.balance, "Bankroll", "midleft", 34)
        self.comp_button = self.button(
            (330, 642, 320, 52),
            f"CLAIM FREE {fmt(dollars(1_000))}",
            self._claim_comp,
            kind="primary",
            font_size=20,
        )
        self.button(
            (700, 646, 140, 48), "STATS", self._overlay("stats"), hotkey=pygame.K_s, font_size=20
        )
        self.button(
            (852, 646, 180, 48),
            "SETTINGS",
            self._overlay("settings"),
            hotkey=pygame.K_o,
            font_size=20,
        )
        self.button(
            (theme.WIDTH - 226, 646, 180, 48), "LEAVE", self.app.quit, kind="danger", font_size=20
        )

    def _overlay(self, name: str) -> Callable[[], None]:
        def push() -> None:
            self.app.scenes.push(self.app.make_scene(name))

        return push

    def _claim_comp(self) -> None:
        amount = self.app.casino.claim_comp()
        if amount:
            self.sound.play("chip_cascade")
            self.sound.play("win")
            self.toast.show(f"Compliments of the house: {fmt(amount)} in chips", theme.GOLD_LIGHT)
            chips = [chip_top(d, 34) for d in (dollars(25), dollars(100), dollars(500))]
            self.particles.sprite_fountain((490, 650), chips, 24)
            self.particles.burst((490, 650), 50, (theme.GOLD, theme.GOLD_LIGHT))
            self.app.save()

    def _open(self, spot: TableSpot) -> None:
        if spot.info.key in REGISTRY:
            self.sound.play("chip_stack", 0.7)
            self.app.go(spot.info.key)
        else:
            self.sound.play("ui_error", 0.6)
            self.toast.show(f"{spot.info.title.title()} opens soon", theme.GOLD_LIGHT)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if super().handle_event(event):
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.go("title")
            return True
        if event.type == pygame.MOUSEMOTION:
            for spot in self.tables:
                inside = spot.rect.collidepoint(event.pos)
                if inside and not spot.hovered:
                    self.sound.play("ui_hover", 0.7)
                spot.hovered = inside
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for spot in self.tables:
                if spot.rect.collidepoint(event.pos):
                    self._open(spot)
                    return True
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self._open(self.tables[event.key - pygame.K_1])
            return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        for spot in self.tables:
            spot.update(dt)
        self.balance.set(self.app.casino.balance)
        self.balance.update(dt)
        self.comp_button.visible = self.app.casino.comp_available

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        crown(surface, (theme.WIDTH // 2 - 250, 40), 40)
        crown(surface, (theme.WIDTH // 2 + 250, 40), 40)
        self.logo.draw(surface, (theme.WIDTH // 2, 42))
        for spot in self.tables:
            spot.draw(surface, self.t, spot.info.key in REGISTRY)
        self.balance.draw(surface)
        self.draw_buttons(surface)
        self.draw_celebration(surface)
        self.draw_overlays(surface)
