"""Title screen: the marquee sign strikes up, then the doors open."""

from __future__ import annotations

import math

import pygame

from ... import __version__
from .. import fonts, theme
from ..fx.glow import neon_text
from ..fx.signboard import SignBoard
from ..render.backdrop import casino_night
from ..stage import Stage

HORIZON = 470


class TitleScene(Stage):
    def enter(self) -> None:
        self.backdrop = casino_night(HORIZON)
        self.sign = SignBoard(
            pygame.Rect(120, 64, 1040, 320),
            "NEON ROYALE",
            self.app.rng,
            title_size=104,
            subtitle="CASINO",
            subtitle_size=46,
            on_strike=lambda: self.sound.play("neon_buzz", 0.5),
            dying_letter=7,
        )
        self.sign.power_on(delay=0.5, duration=1.5)
        self.prompt = neon_text("CLICK OR PRESS ANY KEY", "display", 28, theme.CYAN, 10)
        self.footer = fonts.get("body", 18).render(
            f"Play money only. No real-money gambling, no purchases.   v{__version__}",
            True,
            theme.TEXT_MUTED,
        )
        self.sparkle_timer = 0.0
        self.leaving = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
            return True
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if not self.sign.lit:
                self.sign.skip_intro()
            elif not self.leaving:
                self.leaving = True
                self.sound.play("ui_click")
                self.sign.celebrate(1.0)
                self.app.go("lobby")
            return True
        return False

    def update(self, dt: float) -> None:
        super().update(dt)
        self.sign.update(dt)
        if not self.sound.is_looping("ambience"):
            self.sound.loop("ambience", 0.8, fade_ms=2500)
        if self.sign.lit:
            self.sparkle_timer -= dt
            if self.sparkle_timer <= 0:
                self.sparkle_timer = self.app.rng.uniform(0.25, 0.7)
                r = self.sign.rect
                corner = self.app.rng.choice([r.topleft, r.topright, r.bottomleft, r.bottomright])
                self.particles.burst(
                    corner,
                    count=10,
                    colors=(theme.GOLD, theme.WARM_WHITE, theme.PINK),
                    speed=(40, 160),
                    gravity=120,
                    life=(0.4, 0.9),
                )

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.backdrop, (0, 0))
        self.sign.draw(surface)
        if self.sign.lit:
            pulse = 0.8 + 0.2 * math.sin(self.t * 3.2)
            self.prompt.draw(surface, (theme.WIDTH // 2, 560), pulse)
        surface.blit(
            self.footer, self.footer.get_rect(midbottom=(theme.WIDTH // 2, theme.HEIGHT - 14))
        )
        self.draw_overlays(surface)
