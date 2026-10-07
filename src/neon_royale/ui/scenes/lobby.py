"""Casino floor: pick a game."""

from __future__ import annotations

import pygame

from ...core.money import fmt
from .. import fonts, theme
from ..scene import Scene

GAMES = (
    ("roulette", "ROULETTE", theme.PINK),
    ("blackjack", "BLACKJACK", theme.CYAN),
    ("poker", "HOLD'EM", theme.GOLD),
)


class LobbyScene(Scene):
    def enter(self) -> None:
        width, height, gap = 300, 360, 60
        left = (theme.WIDTH - (3 * width + 2 * gap)) // 2
        self.doors = [
            (key, label, color, pygame.Rect(left + i * (width + gap), 220, width, height))
            for i, (key, label, color) in enumerate(GAMES)
        ]
        self.hover: str | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.go("title")
        elif event.type == pygame.MOUSEMOTION:
            self.hover = next((k for k, _, _, r in self.doors if r.collidepoint(event.pos)), None)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.NIGHT)
        heading = fonts.get("display", 44).render("CHOOSE YOUR TABLE", True, theme.TEXT)
        surface.blit(heading, heading.get_rect(center=(theme.WIDTH // 2, 110)))
        balance = fonts.get("body_bold", 28).render(
            f"Bankroll  {fmt(self.app.casino.balance)}", True, theme.GOLD
        )
        surface.blit(balance, balance.get_rect(center=(theme.WIDTH // 2, 165)))
        for key, label, color, rect in self.doors:
            width = 5 if key == self.hover else 2
            pygame.draw.rect(surface, theme.NIGHT_HI, rect, border_radius=18)
            pygame.draw.rect(surface, color, rect, width, border_radius=18)
            text = fonts.get("display", 34).render(label, True, color)
            surface.blit(text, text.get_rect(center=rect.center))
            soon = fonts.get("body", 20).render("Opening soon", True, theme.TEXT_DIM)
            surface.blit(soon, soon.get_rect(center=(rect.centerx, rect.centery + 44)))
