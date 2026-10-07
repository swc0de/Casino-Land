"""Neon glow: blurred halos around bright "tube" cores.

Blurring is the expensive step, so every glowing graphic is built once and cached.
Per frame we only blit the cached halo and core with an alpha that sets brightness,
which is how flicker and power-on effects stay cheap at 60 FPS.
"""

from __future__ import annotations

import pygame

from .. import fonts
from ..caches import optimise, surface_cache
from ..theme import Color, lerp_color, scale_color


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


class NeonGraphic:
    """A glowing shape: dark tube when off, coloured halo and hot core when lit."""

    def __init__(self, mask: pygame.Surface, color: Color, radius: int = 12) -> None:
        self.color = color
        self.margin = radius * 2
        padded = pad(mask, self.margin)
        self.size = padded.get_size()

        colored = tint(padded, color)
        wide = soft_blur(colored, radius)
        tight = soft_blur(colored, max(2, radius // 3))
        halo = pygame.Surface(self.size, pygame.SRCALPHA)
        halo.blit(wide, (0, 0))
        halo.blit(wide, (0, 0))  # thin strokes blur faint; stacking restores intensity
        halo.blit(tight, (0, 0))
        self.halo = optimise(halo)

        core = colored.copy()
        core.blit(tint(padded, lerp_color(color, (255, 255, 255), 0.55)), (0, 0))
        self.core = core
        self.tube = tint(padded, scale_color(color, 0.28))

    def draw(
        self,
        surface: pygame.Surface,
        center: tuple[float, float],
        intensity: float = 1.0,
        halo_strength: float = 1.0,
    ) -> pygame.Rect:
        rect = self.halo.get_rect(center=(round(center[0]), round(center[1])))
        level = max(0.0, min(1.0, intensity))
        if level < 1.0:
            surface.blit(self.tube, rect)
        if level > 0.0:
            self.halo.set_alpha(round(255 * level * max(0.0, min(1.0, halo_strength))))
            surface.blit(self.halo, rect)
            self.core.set_alpha(round(255 * level))
            surface.blit(self.core, rect)
        return rect

    @property
    def content_size(self) -> tuple[int, int]:
        return self.size[0] - 2 * self.margin, self.size[1] - 2 * self.margin


@surface_cache(maxsize=256)
def neon_text(text: str, role: str, size: int, color: Color, radius: int = 12) -> NeonGraphic:
    mask = fonts.get(role, size).render(text, True, (255, 255, 255))
    return NeonGraphic(mask, color, radius)


@surface_cache(maxsize=64)
def neon_frame(
    size: tuple[int, int],
    color: Color,
    width: int = 4,
    corner: int = 18,
    radius: int = 12,
) -> NeonGraphic:
    """A glowing rounded-rectangle outline, e.g. around a door or panel."""
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255), mask.get_rect(), width, border_radius=corner)
    return NeonGraphic(mask, color, radius)


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
