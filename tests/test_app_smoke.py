"""Headless checks that the window, loop and every scene run without errors."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from neon_royale.__main__ import main
from neon_royale.ui.app import App, AppOptions
from neon_royale.ui.scene import Scene, SceneManager
from neon_royale.ui.scenes import REGISTRY


def _post_click(pos: tuple[int, int]) -> None:
    for kind in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        data = {"pos": pos}
        if kind == pygame.MOUSEMOTION:
            data |= {"rel": (0, 0), "buttons": (0, 0, 0)}
        else:
            data["button"] = 1
        pygame.event.post(pygame.event.Event(kind, data))


@pytest.mark.parametrize("scene", sorted(REGISTRY))
def test_each_scene_runs(scene: str, tmp_path: Path) -> None:
    shot = tmp_path / f"{scene}.png"
    app = App(AppOptions(smoke_seconds=0.4, start_scene=scene, screenshot=shot, mute=True))
    assert app.run() == 0
    assert shot.exists()


def test_cli_smoke_run(tmp_path: Path) -> None:
    save = tmp_path / "save.json"
    assert main(["--smoke", "0.3", "--mute", "--save", str(save)]) == 0
    assert save.exists()


def test_unknown_scene_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown scene"):
        App(AppOptions(smoke_seconds=0.1, start_scene="slots", mute=True)).run()


class _Recorder(Scene):
    def __init__(self, app: App, log: list[str], name: str) -> None:
        super().__init__(app)
        self.log, self.name = log, name

    def enter(self) -> None:
        self.log.append(f"enter {self.name}")

    def exit(self) -> None:
        self.log.append(f"exit {self.name}")

    def handle_event(self, event: pygame.event.Event) -> None:
        self.log.append(f"event {self.name}")


def test_scene_manager_fades_and_swaps_at_midpoint() -> None:
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    log: list[str] = []
    manager = SceneManager()
    manager.switch(_Recorder(None, log, "a"))  # type: ignore[arg-type]
    assert log == ["enter a"]

    manager.switch(_Recorder(None, log, "b"), fade=1.0)  # type: ignore[arg-type]
    manager.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    assert "event a" not in log, "input is ignored during a fade"
    manager.update(0.4)
    assert log == ["enter a"]
    manager.update(0.2)
    assert log == ["enter a", "exit a", "enter b"]
    manager.update(0.5)
    assert not manager.transitioning
    manager.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    assert log[-1] == "event b"


def test_title_click_skips_intro_then_enters_lobby() -> None:
    app = App(AppOptions(mute=True))
    app.scenes.switch(app.make_scene("title"))
    _post_click((640, 360))  # first click skips the sign's power-on intro
    _pump(app)
    _post_click((640, 360))
    for _ in range(60):
        for event in pygame.event.get():
            app._handle_event(event)
        app.scenes.update(1 / 60)
    assert type(app.scenes.top).__name__ == "LobbyScene"
    pygame.quit()


def _pump(app: App, frames: int = 2) -> None:
    for _ in range(frames):
        for event in pygame.event.get():
            app._handle_event(event)
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)


def test_lobby_comp_and_closed_tables() -> None:
    from neon_royale.core.save import COMP_AMOUNT

    app = App(AppOptions(mute=True))
    app.casino.wallet.debit(app.casino.balance)
    app.scenes.switch(app.make_scene("lobby"))
    lobby = app.scenes.top
    _pump(app)
    assert lobby.comp_button.visible
    _post_click(lobby.comp_button.rect.center)
    _pump(app)
    assert app.casino.balance == COMP_AMOUNT
    _pump(app)
    assert not lobby.comp_button.visible

    closed = [c for c in lobby.tables if c.info.key not in REGISTRY]
    if closed:
        _post_click(closed[0].rect.center)
        _pump(app)
        assert lobby.toast.items, "a closed table explains itself"
    pygame.quit()
