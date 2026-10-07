"""Procedurally drawn casino chips: flat (top view) and stacked (2.5D)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from ...core.chips import DENOMINATIONS, break_into_chips
from ...core.money import Cents, dollars
from .. import fonts
from ..caches import optimise, surface_cache
from ..theme import Color, lerp_color, scale_color

SS = 3
SQUASH = 0.5  # vertical squash of a chip seen at the table's viewing angle
THICKNESS = 0.085  # chip edge height as a fraction of diameter


@dataclass(frozen=True)
class ChipStyle:
    base: Color
    spot: Color
    text: Color
    label: str


STYLES: dict[Cents, ChipStyle] = {
    50: ChipStyle((236, 150, 190), (255, 255, 255), (90, 20, 60), "50¢"),
    dollars(1): ChipStyle((236, 236, 240), (36, 92, 214), (36, 92, 214), "1"),
    dollars(5): ChipStyle((206, 30, 44), (255, 255, 255), (255, 255, 255), "5"),
    dollars(25): ChipStyle((20, 140, 74), (255, 255, 255), (255, 255, 255), "25"),
    dollars(100): ChipStyle((30, 30, 38), (255, 255, 255), (255, 255, 255), "100"),
    dollars(500): ChipStyle((114, 46, 182), (255, 214, 90), (255, 255, 255), "500"),
    dollars(1_000): ChipStyle((246, 182, 32), (48, 32, 16), (48, 32, 16), "1K"),
    dollars(5_000): ChipStyle((150, 58, 40), (245, 226, 190), (245, 226, 190), "5K"),
    dollars(25_000): ChipStyle((28, 60, 146), (255, 120, 190), (255, 255, 255), "25K"),
}
assert set(STYLES) == set(DENOMINATIONS)


def _annular_sector(
    c: tuple[float, float], r0: float, r1: float, a0: float, a1: float, steps: int = 8
) -> list[tuple[float, float]]:
    outer = [
        (
            c[0] + math.cos(a0 + (a1 - a0) * i / steps) * r1,
            c[1] + math.sin(a0 + (a1 - a0) * i / steps) * r1,
        )
        for i in range(steps + 1)
    ]
    inner = [
        (
            c[0] + math.cos(a1 - (a1 - a0) * i / steps) * r0,
            c[1] + math.sin(a1 - (a1 - a0) * i / steps) * r0,
        )
        for i in range(steps + 1)
    ]
    return outer + inner


@surface_cache(maxsize=64)
def chip_top(denom: Cents, diameter: int) -> pygame.Surface:
    """A chip seen from directly above."""
    style = STYLES[denom]
    d = diameter * SS
    r = d / 2
    c = (r, r)
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(surf, scale_color(style.base, 0.7), c, r)
    pygame.draw.circle(surf, style.base, c, r * 0.95)

    # Edge inserts: six spots, each split by a thin stripe of the base colour.
    for i in range(6):
        mid = i * math.tau / 6
        span = math.radians(12)
        pygame.draw.polygon(
            surf, style.spot, _annular_sector(c, r * 0.74, r * 0.95, mid - span, mid + span)
        )
        stripe = math.radians(2.2)
        pygame.draw.polygon(
            surf, style.base, _annular_sector(c, r * 0.74, r * 0.95, mid - stripe, mid + stripe, 2)
        )

    # Inlay with a dashed ring.
    pygame.draw.circle(surf, scale_color(style.base, 0.8), c, r * 0.7)
    pygame.draw.circle(surf, lerp_color(style.base, (255, 255, 255), 0.1), c, r * 0.64)
    for i in range(24):
        a = i * math.tau / 24
        p0 = (c[0] + math.cos(a) * r * 0.6, c[1] + math.sin(a) * r * 0.6)
        p1 = (c[0] + math.cos(a + 0.12) * r * 0.6, c[1] + math.sin(a + 0.12) * r * 0.6)
        pygame.draw.line(surf, style.spot, p0, p1, max(1, round(SS * diameter / 40)))

    font_size = round(r * (0.62 if len(style.label) <= 2 else 0.5))
    label = fonts.get("numbers", font_size).render(style.label, True, style.text)
    max_w = r * 1.0
    if label.get_width() > max_w:
        scale = max_w / label.get_width()
        label = pygame.transform.smoothscale(
            label, (round(label.get_width() * scale), round(label.get_height() * scale))
        )
    surf.blit(label, label.get_rect(center=(r, r + r * 0.04)))

    # Soft top-left sheen.
    sheen = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.ellipse(sheen, (255, 255, 255, 34), (d * 0.12, d * 0.08, d * 0.55, d * 0.4))
    surf.blit(sheen, (0, 0))

    small = pygame.transform.smoothscale(surf, (diameter, diameter))
    return optimise(small)


@surface_cache(maxsize=64)
def chip_piece(denom: Cents, diameter: int) -> pygame.Surface:
    """One chip of a stack: squashed top face plus its visible edge band."""
    style = STYLES[denom]
    d = diameter * SS
    face_h = round(d * SQUASH)
    band = round(d * THICKNESS)
    surf = pygame.Surface((d, face_h + band), pygame.SRCALPHA)
    edge = scale_color(style.base, 0.62)
    pygame.draw.ellipse(surf, edge, (0, band, d, face_h))
    pygame.draw.rect(surf, edge, (0, face_h / 2, d, band))

    # Edge stripes where the spots wrap round the rim (front half only).
    r = d / 2
    for i in range(12):
        theta = (i + 0.5) * math.tau / 12
        if math.cos(theta) <= 0.15:
            continue
        x = r + r * math.sin(theta)
        w = max(SS, r * 0.32 * math.cos(theta))
        y_mid = face_h / 2 + band / 2 + (face_h / 2) * math.cos(theta) * 0.98
        rect = pygame.Rect(0, 0, w, band * 0.9)
        rect.center = (round(x), round(y_mid))
        pygame.draw.rect(surf, scale_color(style.spot, 0.85), rect)

    top = pygame.transform.smoothscale(chip_top(denom, diameter), (d, face_h))
    surf.blit(top, (0, 0))
    out = pygame.transform.smoothscale(surf, (diameter, round((face_h + band) / SS)))
    return optimise(out)


@surface_cache(maxsize=16)
def stack_shadow(diameter: int) -> pygame.Surface:
    w, h = round(diameter * 1.5), round(diameter * SQUASH * 1.3)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 120), surf.get_rect().inflate(-w * 0.25, -h * 0.25))
    for _ in range(3):
        surf = pygame.transform.box_blur(surf, max(1, diameter // 12))
    return surf


def chip_step(diameter: int) -> float:
    """Vertical distance between chips in a stack."""
    return max(2.0, diameter * THICKNESS)


def draw_stack(
    surface: pygame.Surface,
    chips: list[Cents],
    bottom_center: tuple[float, float],
    diameter: int,
    shadow: bool = True,
) -> pygame.Rect:
    """Draw ``chips`` (bottom first) as one column. Returns the area covered."""
    x, y = bottom_center
    face_h = diameter * SQUASH
    if shadow:
        sh = stack_shadow(diameter)
        surface.blit(
            sh, sh.get_rect(center=(x + diameter * 0.06, y - face_h / 2 + diameter * 0.08))
        )
    step = chip_step(diameter)
    top_y = y
    for i, denom in enumerate(chips):
        piece = chip_piece(denom, diameter)
        top_y = y - piece.get_height() - i * step
        surface.blit(piece, (round(x - diameter / 2), round(top_y)))
    return pygame.Rect(round(x - diameter / 2), round(top_y), diameter, round(y - top_y))


def stack_columns(amount: Cents, per_column: int = 10, max_columns: int = 4) -> list[list[Cents]]:
    """Split the chips for ``amount`` into columns of at most ``per_column`` chips."""
    chips = break_into_chips(amount)
    if not chips:
        return []
    columns = [chips[i : i + per_column] for i in range(0, len(chips), per_column)]
    return columns[:max_columns]


def draw_amount(
    surface: pygame.Surface,
    amount: Cents,
    bottom_center: tuple[float, float],
    diameter: int,
    per_column: int = 10,
) -> pygame.Rect:
    """Draw ``amount`` as one or more neat columns of chips centred on ``bottom_center``."""
    columns = stack_columns(amount, per_column)
    if not columns:
        return pygame.Rect(round(bottom_center[0]), round(bottom_center[1]), 0, 0)
    gap = diameter * 1.04
    left = bottom_center[0] - gap * (len(columns) - 1) / 2
    area: pygame.Rect | None = None
    for i, column in enumerate(columns):
        rect = draw_stack(surface, column, (left + i * gap, bottom_center[1]), diameter)
        area = rect if area is None else area.union(rect)
    assert area is not None
    return area
