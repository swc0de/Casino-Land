"""Neon signs with believable flicker and power-on sequences."""

from __future__ import annotations

import math
import random
from collections.abc import Callable

import pygame

from .. import fonts
from ..theme import Color
from .glow import NeonGraphic, neon_text

Segment = tuple[float, float]  # (seconds, brightness)

_STUTTERS: tuple[tuple[Segment, ...], ...] = (
    ((0.05, 0.15), (0.04, 1.0), (0.06, 0.1)),
    ((0.03, 0.35), (0.05, 1.0), (0.03, 0.2), (0.08, 0.9)),
    ((0.08, 0.05),),
    ((0.02, 0.5), (0.02, 1.0), (0.02, 0.4)),
)

_SPUTTER: tuple[Segment, ...] = (
    (0.12, 0.05),
    (0.05, 0.7),
    (0.2, 0.08),
    (0.04, 0.9),
    (0.03, 0.1),
    (0.4, 0.85),
    (0.15, 0.0),
)


class Flicker:
    """Brightness of one neon tube over time.

    Tubes burn steadily with a faint breathing, stutter now and then, and a
    ``dying`` tube sputters much more often. ``power_on`` plays the classic
    strike-up: dark, a few hesitant flashes, then lit.
    """

    def __init__(
        self,
        rng: random.Random,
        stutter_rate: float = 0.04,
        dying: bool = False,
        on_stutter: Callable[[], None] | None = None,
    ) -> None:
        """``on_stutter`` is called whenever the tube strikes back on after going dark."""
        self.rng = rng
        self.stutter_rate = 0.6 if dying else stutter_rate
        self.dying = dying
        self.on_stutter = on_stutter
        self.phase = rng.uniform(0, math.tau)
        self.time = 0.0
        self.pattern: list[Segment] = []
        self.segment_left = 0.0
        self.level = 1.0
        self.powered = True

    def power_on(self, delay: float = 0.0) -> None:
        strikes: list[Segment] = [(delay, 0.0)]
        for _ in range(self.rng.randint(1, 3)):
            strikes.append((self.rng.uniform(0.03, 0.07), self.rng.uniform(0.5, 1.0)))
            strikes.append((self.rng.uniform(0.05, 0.18), 0.0))
        strikes.append((0.0, 1.0))
        self._play(strikes)

    def power_off(self) -> None:
        self.pattern.clear()
        self.segment_left = 0.0
        self.level = 0.0
        self.powered = False

    def stutter(self) -> None:
        self._play(list(self.rng.choice(_STUTTERS)))

    def _play(self, pattern: list[Segment]) -> None:
        self.powered = True
        self.pattern = pattern
        self.segment_left = 0.0
        self._advance()  # apply the first segment now, so a tube never flashes on first

    def _advance(self) -> None:
        while self.segment_left <= 0 and self.pattern:
            duration, level = self.pattern.pop(0)
            self.segment_left += duration
            if self.level < 0.3 <= level and self.on_stutter is not None:
                self.on_stutter()  # the tube strikes: a good moment for a buzz
            self.level = level

    def update(self, dt: float) -> None:
        self.time += dt
        if not self.powered:
            return
        self.segment_left -= dt
        self._advance()
        if self.segment_left <= 0 and not self.pattern:
            self.level = 1.0
            if self.rng.random() < self.stutter_rate * dt:
                if self.dying:
                    self._play(list(_SPUTTER))
                else:
                    self.stutter()

    @property
    def value(self) -> float:
        if not self.powered:
            return 0.0
        breathing = 0.965 + 0.035 * math.sin(self.time * 2.1 + self.phase)
        return self.level * breathing


class NeonSign:
    """A word made of individually lit neon letters."""

    def __init__(
        self,
        text: str,
        role: str,
        size: int,
        color: Color,
        rng: random.Random,
        radius: int = 14,
        tracking: int = 0,
        dying_letters: tuple[int, ...] = (),
        stutter_rate: float = 0.03,
        on_stutter: Callable[[], None] | None = None,
    ) -> None:
        font = fonts.get(role, size)
        self.letters: list[tuple[NeonGraphic, float, Flicker]] = []
        x = 0.0
        for i, ch in enumerate(text):
            advance = font.size(text[: i + 1])[0] - font.size(text[:i])[0]
            if not ch.isspace():
                graphic = neon_text(ch, role, size, color, radius)
                flicker = Flicker(
                    rng,
                    stutter_rate=stutter_rate,
                    dying=i in dying_letters,
                    on_stutter=on_stutter,
                )
                self.letters.append((graphic, x + advance / 2, flicker))
            x += advance + tracking
        self.width = x - tracking
        self.height = font.get_height()

    def power_on(self, duration: float = 1.2, delay: float = 0.0) -> None:
        count = max(1, len(self.letters))
        for i, (_, _, flicker) in enumerate(self.letters):
            flicker.power_on(delay + duration * i / count)

    def power_off(self) -> None:
        for _, _, flicker in self.letters:
            flicker.power_off()

    def update(self, dt: float) -> None:
        for _, _, flicker in self.letters:
            flicker.update(dt)

    @property
    def fully_lit(self) -> bool:
        return all(f.powered and not f.pattern and f.level >= 1.0 for _, _, f in self.letters)

    def draw(
        self, surface: pygame.Surface, center: tuple[float, float], boost: float = 1.0
    ) -> None:
        left = center[0] - self.width / 2
        for graphic, x, flicker in self.letters:
            graphic.draw(surface, (left + x, center[1]), flicker.value, halo_strength=boost)
