"""Font loading by role, with caching. All bundled fonts are SIL OFL (see ASSETS.md)."""

from __future__ import annotations

from pathlib import Path

import pygame

from .caches import surface_cache

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

ROLES = {
    "logo": "CinzelDecorative-Black.ttf",  # ornate Roman capitals: the casino's name
    "title": "CinzelDecorative-Bold.ttf",
    "display": "PlayfairDisplaySC-Bold.ttf",  # headings, buttons, numbers
    "display_black": "PlayfairDisplaySC-Black.ttf",
    "body": "Lato-Regular.ttf",
    "body_medium": "Lato-Regular.ttf",
    "body_bold": "Lato-Bold.ttf",
    "body_black": "Lato-Black.ttf",
    "numbers": "Lato-Black.ttf",  # lining figures for chips, pockets and money
}


@surface_cache(maxsize=None)
def get(role: str, size: int) -> pygame.font.Font:
    """Return the font for ``role`` at ``size`` px, falling back to pygame's default."""
    filename = ROLES.get(role)
    if filename is not None:
        path = FONT_DIR / filename
        if path.exists():
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)
