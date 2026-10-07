"""Colours and layout constants: a classic high-roller casino.

Polished wood, padded leather, green baize, brass and gold leaf, ornate carpet.
"""

from __future__ import annotations

WIDTH, HEIGHT = 1280, 720
SIZE = (WIDTH, HEIGHT)
FPS = 60

Color = tuple[int, int, int]

# Room
INK = (10, 6, 5)
WALNUT_DARK = (30, 15, 8)
WALNUT = (66, 33, 16)
MAHOGANY = (104, 40, 22)
CARPET = (92, 12, 26)
CARPET_DARK = (52, 6, 14)
VELVET = (140, 14, 32)
VELVET_DARK = (58, 4, 14)

# Metals
GOLD = (214, 176, 72)
GOLD_LIGHT = (252, 226, 150)
GOLD_DARK = (128, 90, 30)
BRASS = (184, 142, 64)
WARM_WHITE = (255, 240, 205)
WHITE = (255, 255, 255)

# Tables
FELT_GREEN = (16, 98, 56)
FELT_GREEN_DARK = (6, 46, 26)
FELT_BURGUNDY = (104, 16, 30)
FELT_BURGUNDY_DARK = (50, 6, 14)
LEATHER = (26, 20, 18)
LEATHER_HI = (84, 70, 62)

# Text
TEXT = (244, 232, 204)  # cream
TEXT_DIM = (196, 178, 140)
TEXT_MUTED = (140, 122, 96)
INK_TEXT = (40, 24, 10)  # engraved on brass

# Outcomes
WIN = (126, 222, 130)
LOSE = (236, 92, 84)
PUSH = GOLD_LIGHT

# Roulette pockets
ROULETTE_RED = (180, 20, 34)
ROULETTE_BLACK = (20, 18, 20)
ROULETTE_GREEN = (10, 120, 64)


def lerp_color(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def scale_color(c: Color, k: float) -> Color:
    return (min(255, round(c[0] * k)), min(255, round(c[1] * k)), min(255, round(c[2] * k)))
