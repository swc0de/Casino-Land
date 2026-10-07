"""Settings, stats and help overlays, muting, and closing the game safely."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from neon_royale.core import roulette as r
from neon_royale.core.money import dollars
from neon_royale.core.save import STARTING_BANKROLL, load_profile
from neon_royale.ui.app import App, AppOptions


@pytest.fixture
def app():
    application = App(AppOptions(mute=True, seed=2))
    yield application
    pygame.quit()


def pump(app: App, frames: int = 3) -> None:
    for _ in range(frames):
        for event in pygame.event.get():
            app._handle_event(event)
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)


def key(app: App, k: int) -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))
    pump(app)


def test_settings_overlay_changes_and_resets(app: App) -> None:
    app.scenes.switch(app.make_scene("lobby"))
    key(app, pygame.K_o)
    settings_scene = app.scenes.top
    assert type(settings_scene).__name__ == "SettingsScene"
    assert len(app.scenes.stack) == 2, "drawn over the lobby"

    _, master = settings_scene.sliders[0]
    master.on_change(0.25)
    assert app.settings.master_volume == 0.25
    settings_scene._toggle("fast_animations")
    assert app.settings.fast_animations and app.anim_speed > 1

    app.casino.wallet.debit(dollars(9_000))
    settings_scene._reset()
    assert app.casino.balance == dollars(1_000), "first click only asks to confirm"
    settings_scene._reset()
    assert app.casino.balance == STARTING_BANKROLL
    assert app.settings.master_volume == 0.25, "settings survive a reset"

    key(app, pygame.K_ESCAPE)
    assert type(app.scenes.top).__name__ == "LobbyScene"


def test_stats_overlay(app: App) -> None:
    app.casino.record_round("poker", dollars(50), dollars(120))
    app.scenes.switch(app.make_scene("lobby"))
    key(app, pygame.K_s)
    assert type(app.scenes.top).__name__ == "StatsScene"
    pump(app, 5)
    key(app, pygame.K_RETURN)
    assert type(app.scenes.top).__name__ == "LobbyScene"


@pytest.mark.parametrize("game", ["roulette", "blackjack", "poker"])
def test_help_opens_with_f1(app: App, game: str) -> None:
    app.scenes.switch(app.make_scene(game))
    pump(app)
    key(app, pygame.K_F1)
    assert type(app.scenes.top).__name__ == "HelpScene"
    pump(app, 5)
    key(app, pygame.K_F1)
    assert app.scenes.top.help_topic == game


def test_mute_key_toggles_master_volume(app: App) -> None:
    app.scenes.switch(app.make_scene("lobby"))
    app.settings.master_volume = 0.6
    key(app, pygame.K_m)
    assert app.settings.master_volume == 0.0
    key(app, pygame.K_m)
    assert app.settings.master_volume == 0.6


def test_closing_the_window_refunds_bets_on_the_layout(tmp_path: Path) -> None:
    save = tmp_path / "save.json"
    app = App(AppOptions(mute=True, save_path=save))
    app.scenes.switch(app.make_scene("roulette"))
    scene = app.scenes.top
    scene.rack.select(3)
    scene.place(r.straight(7))
    assert app.casino.balance == STARTING_BANKROLL - dollars(100)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.run()
    assert load_profile(save).balance == STARTING_BANKROLL


def test_closing_mid_poker_hand_cashes_out(tmp_path: Path) -> None:
    save = tmp_path / "save.json"
    app = App(AppOptions(mute=True, save_path=save))
    app.scenes.switch(app.make_scene("poker"))
    scene = app.scenes.top
    scene.sit_down()
    pump(app, 90)
    assert scene.room.table.in_hand, "sitting down starts a hand"
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.run()
    assert load_profile(save).balance == STARTING_BANKROLL
