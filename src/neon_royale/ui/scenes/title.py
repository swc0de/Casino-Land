"""Title screen."""

from __future__ import annotations

import math

import pygame

from ... import __version__
from .. import fonts, theme
from ..scene import Scene


class TitleScene(Scene):
    def enter(self) -> None:
        self.t = 0.0
        self.title = fonts.get("marquee", 104).render("NEON ROYALE", True, theme.PINK)
        self.subtitle = fonts.get("display", 40).render("CASINO", True, theme.CYAN)
        self.prompt = fonts.get("body_bold", 28).render(
            "Click or press any key to enter", True, theme.TEXT
        )
        self.footer = fonts.get("body", 18).render(
            f"Play money only. No real-money gambling.   v{__version__}", True, theme.TEXT_MUTED
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
        elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.go("lobby")

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.NIGHT)
        cx = theme.WIDTH // 2
        surface.blit(self.title, self.title.get_rect(center=(cx, 280)))
        surface.blit(self.subtitle, self.subtitle.get_rect(center=(cx, 380)))
        pulse = 0.55 + 0.45 * math.sin(self.t * 3.0)
        self.prompt.set_alpha(round(255 * pulse))
        surface.blit(self.prompt, self.prompt.get_rect(center=(cx, 520)))
        surface.blit(self.footer, self.footer.get_rect(midbottom=(cx, theme.HEIGHT - 16)))
