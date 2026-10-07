"""Colours and layout constants for the neon look."""

from __future__ import annotations

WIDTH, HEIGHT = 1280, 720
SIZE = (WIDTH, HEIGHT)
FPS = 60

Color = tuple[int, int, int]

# Night-sky backdrop
INK = (6, 3, 16)
NIGHT = (14, 8, 34)
NIGHT_HI = (32, 16, 66)

# Neon tubes
PINK = (255, 46, 136)
HOT_PINK = (255, 92, 170)
CYAN = (20, 230, 255)
ELECTRIC_BLUE = (60, 120, 255)
PURPLE = (160, 70, 255)
LIME = (120, 255, 90)
ORANGE = (255, 150, 40)
GOLD = (255, 205, 70)
WARM_WHITE = (255, 244, 214)
WHITE = (255, 255, 255)

# Table felts and fittings
FELT_GREEN = (10, 92, 58)
FELT_GREEN_DARK = (5, 52, 33)
FELT_BLUE = (14, 52, 110)
FELT_BLUE_DARK = (7, 26, 60)
FELT_RED = (110, 16, 36)
FELT_RED_DARK = (58, 7, 20)
RAIL = (52, 24, 14)
RAIL_HI = (120, 64, 30)
BRASS = (196, 150, 72)

# Text
TEXT = (238, 234, 255)
TEXT_DIM = (160, 150, 196)
TEXT_MUTED = (104, 96, 140)

# Outcomes
WIN = (90, 255, 140)
LOSE = (255, 80, 90)
PUSH = (255, 210, 90)

# Roulette pockets
ROULETTE_RED = (196, 24, 42)
ROULETTE_BLACK = (18, 16, 24)
ROULETTE_GREEN = (8, 136, 72)


def lerp_color(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def scale_color(c: Color, k: float) -> Color:
    return (min(255, round(c[0] * k)), min(255, round(c[1] * k)), min(255, round(c[2] * k)))
