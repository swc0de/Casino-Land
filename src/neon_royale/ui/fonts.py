"""Font loading by role, with caching. All bundled fonts are SIL OFL (see ASSETS.md)."""

from __future__ import annotations

from pathlib import Path

import pygame

from .caches import surface_cache

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

ROLES = {
    "marquee": "Monoton-Regular.ttf",  # outlined multi-line neon: big titles only
    "display": "Bungee-Regular.ttf",  # headings, numbers, buttons
    "body": "Rajdhani-SemiBold.ttf",
    "body_medium": "Rajdhani-Medium.ttf",
    "body_bold": "Rajdhani-Bold.ttf",
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
