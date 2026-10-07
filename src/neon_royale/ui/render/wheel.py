"""The roulette wheel: a rotating face (pockets, numbers, cone) inside a static bowl.

Angles are measured in radians clockwise from 12 o'clock. Pocket ``i`` of
``WHEEL_ORDER`` is centred at ``i * POCKET_ANGLE`` on the unrotated face.
"""

from __future__ import annotations

import math

import pygame

from ...core.roulette import POCKETS, WHEEL_ORDER, color_of
from .. import fonts, theme
from ..caches import optimise, surface_cache
from ..theme import lerp_color, scale_color

POCKET_ANGLE = math.tau / POCKETS
SS = 2

# Radii as fractions of the bowl radius.
FACE = 0.80  # the rotating part
NUMBER_RING = (0.80, 1.0)  # of the face radius
POCKET_RING = (0.6, 0.8)  # of the face radius
TRACK = 0.895  # where the ball rolls before it drops
POCKET_BALL = 0.71 * FACE  # where a settled ball sits

POCKET_COLORS = {
    "red": theme.ROULETTE_RED,
    "black": theme.ROULETTE_BLACK,
    "green": theme.ROULETTE_GREEN,
}


def polar(center: tuple[float, float], radius: float, angle: float) -> tuple[float, float]:
    return center[0] + radius * math.sin(angle), center[1] - radius * math.cos(angle)


def _sector(
    center: tuple[float, float], r0: float, r1: float, a0: float, a1: float, steps: int = 6
) -> list[tuple[float, float]]:
    outer = [polar(center, r1, a0 + (a1 - a0) * i / steps) for i in range(steps + 1)]
    inner = [polar(center, r0, a1 - (a1 - a0) * i / steps) for i in range(steps + 1)]
    return outer + inner


@surface_cache(maxsize=4)
def wheel_face(diameter: int) -> pygame.Surface:
    size = diameter * SS
    r = size / 2
    c = (r, r)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    half = POCKET_ANGLE / 2
    font = fonts.get("numbers", round(r * 0.105))
    for i, number in enumerate(WHEEL_ORDER):
        a = i * POCKET_ANGLE
        base = POCKET_COLORS[color_of(number)]
        # Number band.
        pygame.draw.polygon(surf, base, _sector(c, r * NUMBER_RING[0], r, a - half, a + half))
        # Pocket floor, a shade darker.
        pocket = scale_color(base, 0.62)
        pygame.draw.polygon(
            surf, pocket, _sector(c, r * POCKET_RING[0], r * POCKET_RING[1], a - half, a + half)
        )
        label = font.render(str(number), True, theme.WHITE)
        label = pygame.transform.rotozoom(label, -math.degrees(a), 1.0)
        surf.blit(label, label.get_rect(center=polar(c, r * 0.9, a)))
    # Brass frets between pockets.
    for i in range(POCKETS):
        a = i * POCKET_ANGLE + half
        pygame.draw.line(
            surf,
            theme.BRASS,
            polar(c, r * POCKET_RING[0], a),
            polar(c, r * NUMBER_RING[0], a),
            SS * 2,
        )
    pygame.draw.circle(surf, theme.BRASS, c, r * NUMBER_RING[0], SS * 2)
    pygame.draw.circle(surf, (230, 190, 110), c, r, SS * 2)
    # Cone: wood with a soft radial gradient.
    cone_r = r * POCKET_RING[0]
    for k in range(40, 0, -1):
        t = k / 40
        color = lerp_color((44, 20, 10), (122, 62, 26), (1 - t) ** 0.8)
        pygame.draw.circle(surf, color, c, cone_r * t)
    pygame.draw.circle(surf, theme.BRASS, c, cone_r, SS * 2)
    # Turret: four spokes and a cap.
    for k in range(4):
        a = k * math.pi / 2
        end = polar(c, cone_r * 0.62, a)
        pygame.draw.line(surf, (150, 112, 50), c, end, SS * 5)
        pygame.draw.line(surf, theme.GOLD, c, end, SS * 3)
        pygame.draw.circle(surf, theme.GOLD, end, SS * 5)
    pygame.draw.circle(surf, (150, 112, 50), c, cone_r * 0.17)
    pygame.draw.circle(surf, theme.GOLD, c, cone_r * 0.14)
    pygame.draw.circle(
        surf, theme.WARM_WHITE, (c[0] - cone_r * 0.04, c[1] - cone_r * 0.04), cone_r * 0.04
    )
    return optimise(pygame.transform.smoothscale(surf, (diameter, diameter)))


@surface_cache(maxsize=4)
def wheel_bowl(diameter: int) -> pygame.Surface:
    size = diameter * SS
    r = size / 2
    c = (r, r)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # Outer wooden rim.
    for k in range(30, 0, -1):
        t = k / 30
        rim_color = lerp_color((40, 16, 6), (110, 54, 22), math.sin(t * math.pi) ** 0.7)
        pygame.draw.circle(surf, rim_color, c, r * (0.93 + 0.07 * t))
    pygame.draw.circle(surf, theme.BRASS, c, r, SS * 2)
    # Ball track: a polished dark band with a highlight.
    for k in range(24, 0, -1):
        t = k / 24
        track_color = lerp_color((18, 14, 18), (70, 58, 62), (1 - abs(t - 0.5) * 2) ** 2)
        pygame.draw.circle(surf, track_color, c, r * (FACE + (0.93 - FACE) * t))
    pygame.draw.circle(surf, (190, 150, 90), c, r * 0.93, SS)
    # Deflectors ("diamonds") on the slope, alternating orientation.
    for k in range(8):
        a = k * math.tau / 8 + math.tau / 16
        p = polar(c, r * 0.845, a)
        length = r * (0.03 if k % 2 else 0.022)
        pts = [
            polar(p, length * 1.6, a),
            polar(p, length * 0.7, a + math.pi / 2),
            polar(p, length * 1.6, a + math.pi),
            polar(p, length * 0.7, a - math.pi / 2),
        ]
        pygame.draw.polygon(surf, (230, 200, 130), pts)
        pygame.draw.polygon(surf, (120, 90, 40), pts, SS)
    return optimise(pygame.transform.smoothscale(surf, (diameter, diameter)))


@surface_cache(maxsize=4)
def ball_sprite(radius: int) -> pygame.Surface:
    size = radius * 2 * SS + SS * 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (size / 2, size / 2)
    rr = radius * SS
    pygame.draw.circle(surf, (0, 0, 0, 90), (c[0] + SS * 1.5, c[1] + SS * 2), rr)
    for k in range(12, 0, -1):
        t = k / 12
        pygame.draw.circle(surf, lerp_color((255, 255, 255), (170, 170, 185), t**1.5), c, rr * t)
    pygame.draw.circle(surf, (255, 255, 255), (c[0] - rr * 0.35, c[1] - rr * 0.35), rr * 0.28)
    out = pygame.transform.smoothscale(surf, (size // SS, size // SS))
    return optimise(out)
