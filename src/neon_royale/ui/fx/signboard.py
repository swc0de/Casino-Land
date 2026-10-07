"""The Vegas marquee sign: brass-framed board, chasing bulbs, neon lettering."""

from __future__ import annotations

import random
from collections.abc import Callable

import pygame

from .. import theme
from ..caches import optimise
from ..render.backdrop import add_glow, to_surface, vertical_gradient
from ..theme import Color
from .marquee import Marquee
from .neon import NeonSign


def _board(size: tuple[int, int]) -> pygame.Surface:
    w, h = size
    rgb = vertical_gradient(size, (38, 6, 30), (12, 4, 22))
    add_glow(rgb, (w / 2, h * 0.45), w * 0.4, (90, 10, 70), 0.6)
    face = to_surface(rgb)
    board = pygame.Surface(size, pygame.SRCALPHA)
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=26)
    board.blit(face, (0, 0))
    board.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    # Brass frame with an inner lip.
    pygame.draw.rect(board, theme.BRASS, board.get_rect(), 6, border_radius=26)
    pygame.draw.rect(board, (110, 76, 30), board.get_rect().inflate(-12, -12), 2, border_radius=22)
    pygame.draw.rect(board, (250, 210, 130), board.get_rect().inflate(-2, -2), 1, border_radius=26)
    return optimise(board)


class SignBoard:
    def __init__(
        self,
        rect: pygame.Rect,
        title: str,
        rng: random.Random,
        title_size: int = 100,
        title_color: Color = theme.PINK,
        subtitle: str = "",
        subtitle_size: int = 44,
        subtitle_color: Color = theme.CYAN,
        on_strike: Callable[[], None] | None = None,
        bulb_radius: int = 6,
        dying_letter: int | None = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.board = _board(self.rect.size)
        self.marquee = Marquee(
            self.rect.inflate(-26, -26),
            spacing=bulb_radius * 5,
            radius=bulb_radius,
            pattern="chase",
            speed=7,
            rng=rng,
        )
        self.title = NeonSign(
            title,
            "marquee",
            title_size,
            title_color,
            rng,
            radius=16,
            dying_letters=(dying_letter,) if dying_letter is not None else (),
            on_stutter=on_strike,
        )
        self.subtitle = (
            NeonSign(subtitle, "display", subtitle_size, subtitle_color, rng, 12, tracking=8)
            if subtitle
            else None
        )
        has_sub = self.subtitle is not None
        self.title_center = (self.rect.centerx, self.rect.centery - (30 if has_sub else 0))
        self.subtitle_center = (self.rect.centerx, self.rect.centery + self.rect.height * 0.3)
        self.bulbs_on_at = 0.0
        self.time = 0.0

    def power_on(self, delay: float = 0.0, duration: float = 1.4) -> None:
        self.title.power_on(duration, delay)
        if self.subtitle is not None:
            self.subtitle.power_on(0.35, delay + duration + 0.15)
        self.bulbs_on_at = self.time + delay + duration + 0.5
        self.marquee.power = 0.0

    def skip_intro(self) -> None:
        for sign in (self.title, self.subtitle):
            if sign is not None:
                for _, _, flicker in sign.letters:
                    flicker.pattern.clear()
                    flicker.segment_left = 0.0
                    flicker.level = 1.0
                    flicker.powered = True
        self.bulbs_on_at = self.time

    @property
    def lit(self) -> bool:
        """True once the power-on sequence has finished (individual tubes may still flicker)."""
        return self.time >= self.bulbs_on_at

    def celebrate(self, seconds: float = 3.0) -> None:
        self.marquee.celebrate(seconds)

    def update(self, dt: float) -> None:
        self.time += dt
        self.title.update(dt)
        if self.subtitle is not None:
            self.subtitle.update(dt)
        target = 1.0 if self.time >= self.bulbs_on_at else 0.0
        self.marquee.power = min(1.0, self.marquee.power + dt * 3) if target else 0.0
        self.marquee.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.board, self.rect)
        self.marquee.draw(surface)
        self.title.draw(surface, self.title_center)
        if self.subtitle is not None:
            self.subtitle.draw(surface, self.subtitle_center)
