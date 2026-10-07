"""Animated card sprites shared by the card games."""

from __future__ import annotations

import math

import pygame

from ..core.cards import Card
from .fx.glow import neon_frame
from .render.cards import card_back, card_face, card_shadow, card_size
from .theme import Color


class CardSprite:
    """A card on the table. Tween ``pos``, ``flip`` (0 = back, 1 = face), ``angle``
    (degrees), ``scale`` and ``alpha``; the sprite draws itself accordingly."""

    def __init__(
        self,
        card: Card | None,
        pos: tuple[float, float],
        width: int = 96,
        face_up: bool = False,
        angle: float = 0.0,
    ) -> None:
        self.card = card
        self.pos = pos
        self.width = width
        self.flip = 1.0 if face_up else 0.0
        self.angle = angle
        self.scale = 1.0
        self.alpha = 1.0
        self.lift = 0.0  # small vertical offset, e.g. the dealer peeking
        self.highlight: Color | None = None
        self.dim = 0.0

    @property
    def size(self) -> tuple[int, int]:
        return card_size(self.width)

    def _image(self) -> pygame.Surface:
        showing_face = self.flip >= 0.5 and self.card is not None
        image = card_face(self.card, self.width) if showing_face else card_back(self.width)
        squeeze = abs(math.cos(math.pi * self.flip))
        if squeeze < 0.999 or self.scale != 1.0:
            w, h = image.get_size()
            image = pygame.transform.smoothscale(
                image, (max(1, round(w * squeeze * self.scale)), max(1, round(h * self.scale)))
            )
        if abs(self.angle) > 0.05:
            image = pygame.transform.rotozoom(image, self.angle, 1.0)
        if self.dim > 0:
            image = image.copy()
            k = round(255 * (1 - 0.55 * self.dim))
            image.fill((k, k, k, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return image

    def draw(self, surface: pygame.Surface) -> None:
        if self.alpha <= 0.01:
            return
        x, y = self.pos
        y -= self.lift
        if self.highlight is not None:
            w, h = self.size
            frame = neon_frame((w + 8, h + 8), self.highlight, 3, 10, 10)
            frame.draw(surface, (x, y), 0.9)
        shadow = card_shadow(self.width)
        if abs(self.angle) > 0.05:
            shadow = pygame.transform.rotozoom(shadow, self.angle, 1.0)
        image = self._image()
        if self.alpha < 0.99:
            shadow = shadow.copy()
            shadow.set_alpha(round(255 * self.alpha))
            image = image.copy() if image.get_flags() & pygame.SRCALPHA else image
            image.set_alpha(round(255 * self.alpha))
        surface.blit(shadow, shadow.get_rect(center=(x + 4, y + 6)))
        surface.blit(image, image.get_rect(center=(round(x), round(y))))
