"""Screens: title, lobby and one per game."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import App
    from ..scene import Scene

# name -> "module:Class", imported lazily so a scene's heavy assets load only when used.
REGISTRY = {
    "title": "title:TitleScene",
    "lobby": "lobby:LobbyScene",
}


def create_scene(name: str, app: App) -> Scene:
    try:
        target = REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown scene {name!r}; choose from {sorted(REGISTRY)}") from None
    module_name, class_name = target.split(":")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, class_name)(app)
