"""Static backgrounds: gradients, vignette, grain and table felt.

These are rendered once per scene (numpy for per-pixel work) and blitted every frame.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from .. import theme
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
