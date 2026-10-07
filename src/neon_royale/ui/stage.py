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

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.anim = Animator()
        self.director = Director()
        self.particles = ParticleSystem(app.rng)
        self.banner = Banner()
        self.toast = Toast()
        self.buttons: list[Button] = []
        self.t = 0.0

    @property
    def sound(self) -> SoundBank:
        return self.app.sound

    def button(self, *args, **kwargs) -> Button:
        """Create a button wired to the sound bank and register it with the scene."""
        kwargs.setdefault("sounds", self.sound)
        button = Button(*args, **kwargs)
        self.buttons.append(button)
        return button

    def handle_event(self, event: pygame.event.Event) -> bool:  # type: ignore[override]
        used = False
        for button in self.buttons:
            used = button.handle_event(event) or used
            if used and event.type != pygame.MOUSEMOTION:
                return True
        return used

    def update(self, dt: float) -> None:
        self.t += dt
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
