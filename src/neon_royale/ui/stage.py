"""Base class for screens that use the shared presentation toolkit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

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
        self.button((164, 24, 50, 44), "?", self.show_help, color=self.help_color, font_size=22)

    help_color = (20, 230, 255)

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
