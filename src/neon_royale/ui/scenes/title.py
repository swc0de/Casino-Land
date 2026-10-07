"""Title screen: the entrance sign over red velvet, bulbs chasing round it."""

from __future__ import annotations

import math

import pygame

from ... import __version__
from .. import fonts, theme
from ..fx.marquee import Marquee
from ..fx.tween import ease_out_cubic
from ..render.decor import (
    crown,
    engraved_text,
    lacquer_panel,
    ornament_rule,
    scatter_sparkles,
    velvet,
)
from ..stage import Stage

SIGN = pygame.Rect(170, 92, 940, 380)
INTRO = 1.8  # seconds until the sign is fully lit


class TitleScene(Stage):
    def enter(self) -> None:
        self.backdrop = velvet()
        self.marquee = Marquee(
            SIGN.inflate(-24, -24),
            spacing=30,
            radius=6,
            pattern="chase",
            speed=7,
            rng=self.app.rng,
        )
        self.marquee.power = 0.0
        self.logo = engraved_text("NEON ROYALE", "logo", 92, "gold", glow=0.5, shadow=5)
        self.subtitle = engraved_text("C  A  S  I  N  O", "display", 40, "cream", shadow=3)
        self.prompt = engraved_text("CLICK TO ENTER", "display", 30, "gold", shadow=2)
        self.footer = fonts.get("body", 17).render(
            f"Play money only. No real-money gambling, no purchases.   v{__version__}",
            True,
            theme.TEXT_DIM,
        )
        self.intro = 0.0
        self.leaving = False
        self.chimed = False

    @property
    def lit(self) -> bool:
        return self.intro >= INTRO

    def skip_intro(self) -> None:
        self.intro = INTRO

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
            return True
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if not self.lit:
                self.skip_intro()
            elif not self.leaving:
                self.leaving = True
                self.sound.play("chip_stack", 0.8)
                self.marquee.celebrate(1.0)
                self.app.go("lobby")
            return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        self.intro = min(INTRO, self.intro + dt)
        # Bulbs come on in the second half of the intro.
        self.marquee.power = max(0.0, min(1.0, (self.intro - INTRO * 0.5) / (INTRO * 0.4)))
        if self.lit and not self.chimed:
            self.chimed = True
            self.sound.play("push", 0.6)
        self.marquee.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.backdrop, (0, 0))
        appear = ease_out_cubic(min(1.0, self.intro / (INTRO * 0.45)))
        if appear > 0.02:
            lacquer_panel(surface, SIGN, (26, 10, 8), round(245 * appear), appear > 0.5, 22)
            pygame.draw.rect(surface, theme.GOLD_DARK, SIGN.inflate(-40, -40), 1, border_radius=14)
        if appear > 0.6:
            self.marquee.draw(surface)
        text_in = ease_out_cubic(max(0.0, min(1.0, (self.intro - 0.35) / 0.8)))
        cx = theme.WIDTH // 2
        crown(surface, (cx, SIGN.top + 74), 74 * max(0.01, text_in))
        self.logo.draw(surface, (cx, SIGN.top + 178), text_in)
        if text_in > 0.5:
            ornament_rule(surface, (cx, SIGN.top + 252), 420)
        self.subtitle.draw(surface, (cx, SIGN.top + 300), text_in)
        if self.lit:
            scatter_sparkles(surface, pygame.Rect(cx - 380, SIGN.top + 140, 760, 80), self.t, 7)
            pulse = 0.8 + 0.2 * math.sin(self.t * 3.0)
            self.prompt.draw(surface, (cx, 560), pulse)
        surface.blit(
            self.footer, self.footer.get_rect(midbottom=(theme.WIDTH // 2, theme.HEIGHT - 16))
        )
        self.draw_overlays(surface)
