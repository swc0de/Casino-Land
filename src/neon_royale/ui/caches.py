"""Caches for pre-rendered surfaces and fonts.

Rendered surfaces and Font objects belong to the pygame session that made them, so
every cache is registered here and cleared together when a new session starts (the
app does this on start-up; tests start many sessions in one process).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any, TypeVar

import pygame

F = TypeVar("F", bound=Callable[..., Any])

_registered: list[Any] = []


def surface_cache(maxsize: int | None = 128) -> Callable[[F], F]:
    """``functools.lru_cache`` that is also cleared by :func:`clear_all`."""

    def decorate(fn: F) -> F:
        cached = lru_cache(maxsize=maxsize)(fn)
        _registered.append(cached)
        return cached  # type: ignore[return-value]

    return decorate


def clear_all() -> None:
    for cached in _registered:
        cached.cache_clear()


def optimise(surface: pygame.Surface) -> pygame.Surface:
    """Convert to the display's pixel format for fast blits, once a window exists."""
    if pygame.display.get_surface() is None:
        return surface
    return surface.convert_alpha()
