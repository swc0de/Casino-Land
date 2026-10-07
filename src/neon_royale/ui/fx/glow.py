"""Glow helpers: soft blurs, padding, tinting and round light sprites.

Blurring is the expensive step, so callers build glowing graphics once and cache them.
"""

from __future__ import annotations

import pygame

from ..caches import surface_cache
from ..theme import Color, lerp_color


def soft_blur(surface: pygame.Surface, radius: int) -> pygame.Surface:
    """Approximate a gaussian blur with three fast box-blur passes."""
    if radius <= 0:
        return surface.copy()
    box = max(1, round(radius / 1.7))
    out = surface
    for _ in range(3):
        out = pygame.transform.box_blur(out, box)
    return out


def pad(surface: pygame.Surface, margin: int) -> pygame.Surface:
    w, h = surface.get_size()
    out = pygame.Surface((w + 2 * margin, h + 2 * margin), pygame.SRCALPHA)
    out.blit(surface, (margin, margin))
    return out


def tint(mask: pygame.Surface, color: Color) -> pygame.Surface:
    """Recolour a white-on-transparent mask, keeping its alpha."""
    out = mask.copy()
    out.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return out


@surface_cache(maxsize=128)
def glow_dot(color: Color, radius: int) -> pygame.Surface:
    """A soft round light, used for sparks and bulbs."""
    size = radius * 6
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    steps = max(4, radius * 2)
    for i in range(steps, 0, -1):
        r = radius * 3 * i / steps
        k = (1 - i / steps) ** 2
        alpha = round(255 * k)
        pygame.draw.circle(surf, (*lerp_color(color, (255, 255, 255), k * 0.7), alpha), (c, c), r)
    return surf
