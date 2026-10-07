"""Lightweight particles: sparks, confetti, and flying chip sprites."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

import pygame

from .. import theme
from ..theme import Color
from .glow import glow_dot

CONFETTI_COLORS: tuple[Color, ...] = (
    theme.PINK,
    theme.CYAN,
    theme.GOLD,
    theme.LIME,
    theme.PURPLE,
    theme.ORANGE,
    theme.WHITE,
)


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    color: Color
    kind: str  # "spark" | "confetti" | "sprite"
    gravity: float = 0.0
    drag: float = 0.0
    rot: float = 0.0
    spin: float = 0.0
    sprite: pygame.Surface | None = None


class ParticleSystem:
    def __init__(self, rng: random.Random | None = None, limit: int = 1200) -> None:
        self.rng = rng or random.Random()
        self.limit = limit
        self.particles: list[Particle] = []

    def __len__(self) -> int:
        return len(self.particles)

    def _add(self, particle: Particle) -> None:
        if len(self.particles) >= self.limit:
            self.particles.pop(0)
        self.particles.append(particle)

    def burst(
        self,
        pos: tuple[float, float],
        count: int = 40,
        colors: Sequence[Color] = (theme.GOLD, theme.WARM_WHITE),
        speed: tuple[float, float] = (120, 420),
        direction: float = -math.pi / 2,
        spread: float = math.tau,
        life: tuple[float, float] = (0.5, 1.1),
        size: tuple[float, float] = (2, 4),
        gravity: float = 500,
        drag: float = 1.2,
    ) -> None:
        """Glowing sparks thrown out from ``pos``."""
        rng = self.rng
        for _ in range(count):
            angle = direction + rng.uniform(-spread / 2, spread / 2)
            v = rng.uniform(*speed)
            lifetime = rng.uniform(*life)
            self._add(
                Particle(
                    pos[0],
                    pos[1],
                    math.cos(angle) * v,
                    math.sin(angle) * v,
                    lifetime,
                    lifetime,
                    rng.uniform(*size),
                    rng.choice(colors),
                    "spark",
                    gravity,
                    drag,
                )
            )

    def confetti(self, area: pygame.Rect, count: int = 120) -> None:
        """Paper confetti fluttering down from the top edge of ``area``."""
        rng = self.rng
        for _ in range(count):
            lifetime = rng.uniform(2.2, 3.6)
            self._add(
                Particle(
                    rng.uniform(area.left, area.right),
                    area.top - rng.uniform(0, 140),
                    rng.uniform(-60, 60),
                    rng.uniform(40, 200),
                    lifetime,
                    lifetime,
                    rng.uniform(5, 9),
                    rng.choice(CONFETTI_COLORS),
                    "confetti",
                    gravity=110,
                    drag=0.9,
                    rot=rng.uniform(0, math.tau),
                    spin=rng.uniform(-9, 9),
                )
            )

    def sprite_fountain(
        self,
        pos: tuple[float, float],
        sprites: Sequence[pygame.Surface],
        count: int = 16,
        speed: tuple[float, float] = (260, 520),
        spread: float = 1.4,
        life: tuple[float, float] = (0.9, 1.4),
    ) -> None:
        """Throw sprites (e.g. chips) upward like a jackpot spill."""
        rng = self.rng
        for _ in range(count):
            angle = -math.pi / 2 + rng.uniform(-spread / 2, spread / 2)
            v = rng.uniform(*speed)
            lifetime = rng.uniform(*life)
            self._add(
                Particle(
                    pos[0],
                    pos[1],
                    math.cos(angle) * v,
                    math.sin(angle) * v,
                    lifetime,
                    lifetime,
                    1.0,
                    theme.WHITE,
                    "sprite",
                    gravity=900,
                    drag=0.3,
                    sprite=rng.choice(sprites),
                )
            )

    def update(self, dt: float) -> None:
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            damping = max(0.0, 1.0 - p.drag * dt)
            p.vx *= damping
            p.vy = p.vy * damping + p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.spin * dt
            alive.append(p)
        self.particles = alive

    def clear(self) -> None:
        self.particles.clear()

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.particles:
            fade = min(1.0, p.life / (p.max_life * 0.35))
            if p.kind == "spark":
                dot = glow_dot(p.color, max(1, round(p.size)))
                dot.set_alpha(round(255 * fade))
                surface.blit(dot, (p.x - dot.get_width() / 2, p.y - dot.get_height() / 2))
            elif p.kind == "confetti":
                w = p.size
                h = max(1.0, p.size * 0.55 * abs(math.cos(p.rot)))
                shade = 0.6 + 0.4 * abs(math.sin(p.rot))
                color = tuple(round(c * shade) for c in p.color)
                pygame.draw.rect(surface, color, (p.x - w / 2, p.y - h / 2, w, h))
            elif p.sprite is not None:
                p.sprite.set_alpha(round(255 * fade))
                rect = p.sprite.get_rect(center=(round(p.x), round(p.y)))
                surface.blit(p.sprite, rect)
                p.sprite.set_alpha(255)
