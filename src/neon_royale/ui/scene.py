"""Scenes (screens) and the stack that switches between them with a fade."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from . import theme

if TYPE_CHECKING:
    from .app import App


class Scene:
    """One screen of the game. Subclasses override only the hooks they need."""

    #: Overlays (pause menus, dialogs) draw on top of the scene beneath them.
    overlay = False

    def __init__(self, app: App) -> None:
        self.app = app

    def enter(self) -> None:
        """Called when the scene becomes active."""

    def exit(self) -> None:
        """Called when the scene is removed from the stack."""

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


class SceneManager:
    """A stack of scenes. ``switch`` fades through black; ``push``/``pop`` are instant."""

    def __init__(self) -> None:
        self.stack: list[Scene] = []
        self._next: Scene | None = None
        self._fade_time = 0.0
        self._fade_elapsed = 0.0
        self._veil = pygame.Surface(theme.SIZE)
        self._veil.fill(theme.INK)

    @property
    def top(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    @property
    def transitioning(self) -> bool:
        return self._next is not None or self._fade_elapsed < self._fade_time

    def switch(self, scene: Scene, fade: float = 0.45) -> None:
        """Replace the whole stack with ``scene``, fading out then in."""
        if not self.stack or fade <= 0:
            self._replace(scene)
            self._fade_time = self._fade_elapsed = 0.0
            return
        self._next = scene
        self._fade_time = fade
        self._fade_elapsed = 0.0

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)
        scene.enter()

    def pop(self) -> None:
        if self.stack:
            self.stack.pop().exit()

    def _replace(self, scene: Scene) -> None:
        while self.stack:
            self.stack.pop().exit()
        self.stack.append(scene)
        scene.enter()

    def handle_event(self, event: pygame.event.Event) -> None:
        # Input is ignored mid-fade so a double click can't act on a vanishing screen.
        if self.top is not None and not self.transitioning:
            self.top.handle_event(event)

    def update(self, dt: float) -> None:
        if self._fade_time > 0:
            half = self._fade_time / 2
            before = self._fade_elapsed
            self._fade_elapsed = min(self._fade_time, self._fade_elapsed + dt)
            if self._next is not None and before < half <= self._fade_elapsed:
                self._replace(self._next)
                self._next = None
            if self._fade_elapsed >= self._fade_time:
                self._fade_time = self._fade_elapsed = 0.0
        if self.top is not None:
            self.top.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        first = len(self.stack) - 1
        while first > 0 and self.stack[first].overlay:
            first -= 1
        for scene in self.stack[max(first, 0) :]:
            scene.draw(surface)
        if self._fade_time > 0:
            half = self._fade_time / 2
            t = self._fade_elapsed
            alpha = t / half if t < half else (self._fade_time - t) / half
            self._veil.set_alpha(round(255 * max(0.0, min(1.0, alpha))))
            surface.blit(self._veil, (0, 0))
