"""Static backgrounds: night sky, bokeh lights, neon floor grid, felt and vignette.

These are rendered once per scene (numpy for per-pixel work) and blitted every frame.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from .. import theme
from ..caches import surface_cache
from ..theme import Color


def to_surface(rgb: np.ndarray) -> pygame.Surface:
    """(h, w, 3) float array in 0..255 -> Surface."""
    data = np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1)
    surf = pygame.surfarray.make_surface(data)
    return surf.convert() if pygame.display.get_init() and pygame.display.get_surface() else surf


def vertical_gradient(size: tuple[int, int], top: Color, bottom: Color) -> np.ndarray:
    w, h = size
    k = np.linspace(0.0, 1.0, h)[:, None, None]
    top_a = np.array(top, dtype=float)[None, None, :]
    bottom_a = np.array(bottom, dtype=float)[None, None, :]
    return np.broadcast_to(top_a + (bottom_a - top_a) * k, (h, w, 3)).copy()


def add_vignette(rgb: np.ndarray, strength: float = 0.55, roundness: float = 1.0) -> np.ndarray:
    h, w, _ = rgb.shape
    y = np.linspace(-1, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :] * roundness
    d = np.sqrt(x * x + y * y) / math.sqrt(1 + roundness * roundness)
    shade = 1.0 - strength * np.clip(d, 0, 1) ** 2.2
    return rgb * shade[:, :, None]


def add_glow(
    rgb: np.ndarray, center: tuple[float, float], radius: float, color: Color, amount: float
) -> None:
    """Add a soft radial light in place."""
    h, w, _ = rgb.shape
    yy, xx = np.ogrid[:h, :w]
    d2 = ((xx - center[0]) ** 2 + (yy - center[1]) ** 2) / (radius * radius)
    falloff = np.exp(-d2) * amount
    rgb += falloff[:, :, None] * np.array(color, dtype=float)[None, None, :]


def add_grain(rgb: np.ndarray, amount: float, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, amount, rgb.shape[:2])
    rgb += noise[:, :, None]


def night_sky(size: tuple[int, int] = theme.SIZE, seed: int = 3) -> pygame.Surface:
    """Deep purple night with distant blurry city lights and a horizon glow."""
    w, h = size
    rgb = vertical_gradient(size, (4, 2, 14), (34, 10, 52))
    add_glow(rgb, (w * 0.5, h * 0.62), w * 0.55, (120, 20, 110), 0.55)
    add_glow(rgb, (w * 0.15, h * 0.2), w * 0.3, (20, 40, 120), 0.35)
    add_glow(rgb, (w * 0.85, h * 0.25), w * 0.3, (90, 20, 120), 0.3)
    add_grain(rgb, 2.0, seed)
    surf = to_surface(add_vignette(rgb, 0.45))
    rng = random.Random(seed)
    bokeh = pygame.Surface(size, pygame.SRCALPHA)
    palette = (theme.PINK, theme.CYAN, theme.GOLD, theme.PURPLE, theme.ORANGE)
    for _ in range(46):
        r = rng.uniform(4, 22)
        x, y = rng.uniform(0, w), rng.uniform(h * 0.05, h * 0.7)
        color = rng.choice(palette)
        pygame.draw.circle(bokeh, (*color, rng.randint(14, 40)), (x, y), r)
        pygame.draw.circle(bokeh, (*color, rng.randint(20, 50)), (x, y), r, 1)
    surf.blit(bokeh, (0, 0))
    return surf


def neon_floor(
    surface: pygame.Surface,
    horizon: int,
    color: Color = theme.PINK,
    spacing: int = 64,
    rows: int = 14,
) -> None:
    """A synthwave perspective grid from ``horizon`` to the bottom of ``surface``."""
    w, h = surface.get_size()
    floor = pygame.Surface((w, h - horizon), pygame.SRCALPHA)
    fh = floor.get_height()
    vanishing_x = w / 2
    lines = pygame.Surface(floor.get_size(), pygame.SRCALPHA)
    for i in range(-24, 25):
        x_bottom = vanishing_x + i * spacing * 2.2
        pygame.draw.line(
            lines, (*color, 150), (vanishing_x + i * spacing * 0.08, 0), (x_bottom, fh), 2
        )
    for j in range(1, rows + 1):
        k = (j / rows) ** 2.2
        y = k * fh
        pygame.draw.line(lines, (*color, round(60 + 160 * k)), (0, y), (w, y), 2)
    glow = lines.copy()
    for _ in range(3):
        glow = pygame.transform.box_blur(glow, 4)
    floor.blit(glow, (0, 0))
    floor.blit(glow, (0, 0))
    floor.blit(lines, (0, 0))
    # Fade into the haze near the horizon.
    fade = pygame.Surface(floor.get_size(), pygame.SRCALPHA)
    for y in range(fh):
        a = round(255 * max(0.0, 1 - y / (fh * 0.45)) ** 1.5)
        pygame.draw.line(fade, (24, 8, 40, a), (0, y), (w, y))
    floor.blit(fade, (0, 0))
    surface.blit(floor, (0, horizon))
    # Horizon line glow.
    band = pygame.Surface((w, 40), pygame.SRCALPHA)
    pygame.draw.line(band, (*color, 220), (0, 20), (w, 20), 3)
    for _ in range(3):
        band = pygame.transform.box_blur(band, 6)
    surface.blit(band, (0, horizon - 20))
    pygame.draw.line(
        surface, theme.lerp_color(color, theme.WHITE, 0.4), (0, horizon), (w, horizon), 1
    )


def felt(
    size: tuple[int, int],
    color: Color = theme.FELT_GREEN,
    dark: Color = theme.FELT_GREEN_DARK,
    seed: int = 1,
) -> pygame.Surface:
    """Casino felt: soft spotlight in the middle, darker edges, fine cloth grain."""
    w, h = size
    rgb = vertical_gradient(size, color, color)
    yy, xx = np.ogrid[:h, :w]
    d = np.sqrt(((xx - w / 2) / (w * 0.62)) ** 2 + ((yy - h * 0.42) / (h * 0.75)) ** 2)
    k = np.clip(d, 0, 1)[:, :, None] ** 1.6
    rgb = rgb * (1 - k) + np.array(dark, dtype=float)[None, None, :] * k
    rng = np.random.default_rng(seed)
    grain = rng.normal(0, 3.2, (h, w))
    weave = (np.sin(xx * 1.9) * np.sin(yy * 1.9)) * 1.2
    rgb += (grain + weave)[:, :, None]
    return to_surface(rgb)


def wood_rail(size: tuple[int, int], seed: int = 2) -> pygame.Surface:
    """Padded leather-and-wood table rail texture."""
    w, h = size
    rgb = vertical_gradient(size, (92, 46, 22), (40, 18, 8))
    rng = np.random.default_rng(seed)
    xx = np.arange(w)[None, :]
    yy = np.arange(h)[:, None]
    streaks = np.sin(xx * 0.035 + np.sin(yy * 0.15) * 2.0 + rng.uniform(0, 6)) * 9
    rgb += streaks[:, :, None] * np.array([1.0, 0.55, 0.3])[None, None, :]
    add_grain(rgb, 3.0, seed)
    return to_surface(rgb)


@surface_cache(maxsize=4)
def casino_night(horizon: int = 470, floor_color: Color = theme.PINK) -> pygame.Surface:
    """The shared lobby/title backdrop: night sky over a glowing neon floor."""
    surf = night_sky()
    neon_floor(surf, horizon, floor_color)
    return surf
