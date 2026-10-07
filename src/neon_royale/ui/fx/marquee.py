"""Vegas marquee bulbs running around a rectangle in chase patterns."""

from __future__ import annotations

import math
import random

import pygame

from .. import theme
from ..caches import optimise, surface_cache
from ..theme import Color, lerp_color, scale_color

LEVELS = 12  # pre-rendered brightness steps per bulb colour

RAINBOW: tuple[Color, ...] = (
    theme.PINK,
    theme.GOLD,
    theme.CYAN,
    theme.LIME,
    theme.PURPLE,
    theme.ORANGE,
)


@surface_cache(maxsize=64)
def bulb_sprites(color: Color, radius: int) -> tuple[pygame.Surface, ...]:
    """Bulb images from unlit glass (index 0) to full blaze (index LEVELS-1)."""
    size = radius * 7
    c = size / 2
    sprites = []
    for level in range(LEVELS):
        k = level / (LEVELS - 1)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Halo: grows and brightens with the bulb.
        if k > 0:
            halo_r = radius * (1.6 + 1.9 * k)
            steps = 10
            for i in range(steps, 0, -1):
                r = halo_r * i / steps
                a = round(150 * k * (1 - i / steps) ** 1.6)
                pygame.draw.circle(surf, (*color, a), (c, c), r)
        # Glass and socket.
        pygame.draw.circle(surf, (24, 16, 12, 255), (c, c), radius + 1.5)
        glass = lerp_color(scale_color(color, 0.22), lerp_color(color, theme.WHITE, 0.6), k)
        pygame.draw.circle(surf, (*glass, 255), (c, c), radius)
        hot = lerp_color(glass, theme.WHITE, 0.4 + 0.5 * k)
        pygame.draw.circle(surf, (*hot, 255), (c, c), radius * (0.35 + 0.3 * k))
        # Specular glint so unlit bulbs still read as glass.
        glint = (255, 255, 255, round(90 + 120 * k))
        pygame.draw.circle(surf, glint, (c - radius * 0.35, c - radius * 0.35), radius * 0.28)
        sprites.append(optimise(surf))
    return tuple(sprites)


def perimeter_points(rect: pygame.Rect, spacing: float) -> list[tuple[float, float]]:
    """Evenly spaced points clockwise around ``rect``, starting at its top-left corner."""
    w, h = rect.width, rect.height
    total = 2 * (w + h)
    count = max(4, round(total / spacing))
    step = total / count
    points = []
    for i in range(count):
        d = i * step
        if d < w:
            points.append((rect.left + d, rect.top))
        elif d < w + h:
            points.append((rect.right, rect.top + d - w))
        elif d < 2 * w + h:
            points.append((rect.right - (d - w - h), rect.bottom))
        else:
            points.append((rect.left, rect.bottom - (d - 2 * w - h)))
    return points


class Marquee:
    """Bulbs around a rectangle. Patterns: chase, alternate, wave, sparkle, steady.

    ``celebrate`` switches to a fast rainbow chase for a few seconds (wins, jackpots)
    and then returns to the normal pattern.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        spacing: float = 26,
        radius: int = 5,
        color: Color = theme.WARM_WHITE,
        pattern: str = "chase",
        speed: float = 6.0,
        rng: random.Random | None = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.points = perimeter_points(self.rect, spacing)
        self.radius = radius
        self.color = color
        self.pattern = pattern
        self.speed = speed
        self.rng = rng or random.Random()
        self.time = 0.0
        self.celebrating = 0.0
        self.sparkle = [0.0] * len(self.points)
        self.power = 1.0

    def celebrate(self, seconds: float = 3.0) -> None:
        self.celebrating = max(self.celebrating, seconds)

    def update(self, dt: float) -> None:
        self.time += dt
        self.celebrating = max(0.0, self.celebrating - dt)
        if self.pattern == "sparkle" or self.celebrating:
            for i in range(len(self.sparkle)):
                self.sparkle[i] = max(0.0, self.sparkle[i] - dt * 2.5)
                if self.rng.random() < dt * 0.9:
                    self.sparkle[i] = 1.0

    def brightness(self, i: int) -> float:
        t = self.time
        n = len(self.points)
        if self.celebrating:
            phase = (i - t * 22) % 4
            return 1.0 if phase < 2 else 0.25 + 0.6 * self.sparkle[i]
        if self.pattern == "chase":
            phase = (i - t * self.speed) % 3
            return 1.0 if phase < 1 else (0.35 if phase < 1.6 else 0.12)
        if self.pattern == "alternate":
            return 1.0 if (i + int(t * self.speed / 2)) % 2 == 0 else 0.15
        if self.pattern == "wave":
            return 0.2 + 0.8 * (0.5 + 0.5 * math.sin(t * self.speed - i * math.tau * 3 / n))
        if self.pattern == "sparkle":
            return 0.3 + 0.7 * self.sparkle[i]
        return 1.0

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        base = bulb_sprites(self.color, self.radius)
        half = base[0].get_width() / 2
        ox, oy = offset
        for i, (x, y) in enumerate(self.points):
            if self.celebrating:
                sprites = bulb_sprites(
                    RAINBOW[(i + int(self.time * 10)) % len(RAINBOW)], self.radius
                )
            else:
                sprites = base
            level = round(self.brightness(i) * self.power * (LEVELS - 1))
            surface.blit(sprites[max(0, min(LEVELS - 1, level))], (x - half + ox, y - half + oy))
