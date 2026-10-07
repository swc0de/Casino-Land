"""Base class for screens that use the shared presentation toolkit."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from . import theme
from .fx.particles import ParticleSystem
from .fx.tween import Animator, Director
from .scene import Scene
from .widgets import Banner, Button, Toast

if TYPE_CHECKING:
    from ..audio.mixer import SoundBank
    from .app import App


class Stage(Scene):
    """A scene with tweens, scripted sequences, particles, banners, toasts and buttons.

    Subclasses call ``super()`` in ``update`` and ``handle_event`` and draw
    ``draw_overlays`` last so effects sit on top of the table.
    """

    #: Level of the casino-floor ambience loop while this scene is showing.
    ambience = 0.8
    #: Key into ``overlays.HELP`` for the rules panel (F1 or the "?" button).
    help_topic: str | None = None

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.anim = Animator()
        self.director = Director()
        self.particles = ParticleSystem(app.rng)
        self.banner = Banner()
        self.toast = Toast()
        self.buttons: list[Button] = []
        self.t = 0.0
        self._ambience_applied = False
        self.glow_time = 0.0
        self.glow_total = 0.0
        self._wash = pygame.Surface(theme.SIZE)

    @property
    def sound(self) -> SoundBank:
        return self.app.sound

    def button(self, *args, **kwargs) -> Button:
        """Create a button wired to the sound bank and register it with the scene."""
        kwargs.setdefault("sounds", self.sound)
        button = Button(*args, **kwargs)
        self.buttons.append(button)
        return button

    def show_help(self) -> None:
        if self.help_topic is not None:
            from .scenes.overlays import open_help

            open_help(self.app, self.help_topic)

    def add_help_button(self) -> None:
        self.button((180, 38, 50, 44), "?", self.show_help, font_size=24)

    def celebrate(self, seconds: float = 2.0, big: bool = False) -> None:
        """The table lights swell and gold sparks fly (wins, blackjacks, jackpots)."""
        self.glow_time = max(self.glow_time, seconds)
        self.glow_total = max(self.glow_total, seconds)
        if big:
            self.particles.confetti(pygame.Rect(0, 0, theme.WIDTH, 40), 150)

    def draw_celebration(self, surface: pygame.Surface) -> None:
        """Warm light wash used by ``celebrate``; call before ``draw_overlays``."""
        if self.glow_time <= 0:
            return
        k = self.glow_time / max(0.01, self.glow_total)
        pulse = 0.5 + 0.5 * math.sin(self.t * 9)
        # Additive blits ignore surface alpha, so scale the colour itself.
        level = 0.22 * k * (0.6 + 0.4 * pulse)
        self._wash.fill((round(120 * level), round(84 * level), round(30 * level)))
        surface.blit(self._wash, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def handle_event(self, event: pygame.event.Event) -> bool:  # type: ignore[override]
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.help_topic:
            self.show_help()
            return True
        used = False
        for button in self.buttons:
            used = button.handle_event(event) or used
            if used and event.type != pygame.MOUSEMOTION:
                return True
        return used

    def update(self, dt: float) -> None:
        self.t += dt
        if self.ambience is not None:
            sound = self.sound
            if not sound.is_looping("ambience"):
                sound.loop("ambience", self.ambience, fade_ms=2000)
            elif not self._ambience_applied:
                sound.set_loop_volume("ambience", self.ambience)
            self._ambience_applied = sound.is_looping("ambience")
        speed = self.app.anim_speed
        self.anim.update(dt * speed)
        self.director.update(dt * speed)
        self.particles.update(dt)
        self.glow_time = max(0.0, self.glow_time - dt)
        self.banner.update(dt)
        self.toast.update(dt)
        for button in self.buttons:
            button.update(dt)

    def draw_buttons(self, surface: pygame.Surface) -> None:
        for button in self.buttons:
            button.draw(surface)

    def draw_overlays(self, surface: pygame.Surface) -> None:
        self.particles.draw(surface)
        self.banner.draw(surface)
        self.toast.draw(surface)
