"""Poker scene played headless: buy-in, hands with the player acting, leaving."""

from __future__ import annotations

import pygame
import pytest

from neon_royale.core.money import dollars
from neon_royale.core.poker.room import HUMAN_SEAT, MIN_BUY_IN
from neon_royale.ui.app import App, AppOptions


@pytest.fixture
def scene():
    app = App(AppOptions(mute=True, seed=12))
    app.settings.fast_animations = True
    app.scenes.switch(app.make_scene("poker"))
    yield app.scenes.top
    pygame.quit()


def step(scene, frames: int = 1, policy: str = "call") -> None:
    app = scene.app
    for _ in range(frames):
        if scene.mode == "human":
            scene.choose(policy)
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)


def test_starts_with_the_buy_in_dialog(scene) -> None:
    assert scene.mode == "buyin"
    assert not scene.room.seated
    assert scene.btn_sit.visible and scene.btn_sit.enabled
    assert scene.buyin_amount >= MIN_BUY_IN


def test_play_several_hands(scene) -> None:
    app = scene.app
    total = app.casino.balance
    scene.buyin_slider.value = 1.0
    scene._buyin_changed(1.0)
    scene.sit_down()
    buy_in = total - app.casino.balance
    assert buy_in == dollars(2_000)
    step(scene, 60 * 90)
    if scene.mode == "buyin":  # busted calling every hand: back to the buy-in dialog
        assert not scene.room.seated
        assert app.casino.balance == total - buy_in
    else:
        assert scene.table.hand_number >= 4
    assert app.casino.profile.stats["poker"].rounds >= 2
    if not scene.table.in_hand:
        for view in scene.seats:
            seat = scene.table.seats[view.index]
            if seat is not None:
                assert view.stack == seat.stack, "display stacks match the engine"


def test_folding_every_hand_only_costs_blinds(scene) -> None:
    app = scene.app
    scene.sit_down()
    start_stack = scene.room.stack
    step(scene, 60 * 40, policy="fold")
    hands = scene.table.hand_number
    assert hands >= 3
    lost = start_stack - scene.room.stack
    if scene.table.in_hand:
        lost -= (
            scene.table.players[HUMAN_SEAT].committed if HUMAN_SEAT in scene.table.players else 0
        )
    assert 0 <= lost <= hands * dollars(15)
    del app


def test_leaving_cashes_out(scene) -> None:
    app = scene.app
    start = app.casino.balance
    scene.sit_down()
    step(scene, 30)
    scene.leave()
    step(scene, 60 * 30, policy="fold")
    assert not scene.room.seated
    assert type(app.scenes.top).__name__ == "LobbyScene" or scene.app.scenes._next is not None
    # Lost at most the blinds and calls of the hand that was running.
    assert start - app.casino.balance <= dollars(30)


def test_raise_controls(scene) -> None:
    scene.sit_down()
    for _ in range(60 * 30):
        if scene.mode == "human":
            break
        step(scene)
    assert scene.mode == "human"
    legal = scene.table.legal()
    scene.quick_bet(-1)
    assert scene.raise_to == legal.max_to
    assert scene.btn_raise.label == "ALL IN" or not legal.can_raise
    scene.quick_bet(0.5)
    assert legal.min_to <= scene.raise_to <= legal.max_to
    scene._raise_changed(0.0)
    assert scene.raise_to == legal.min_to
    scene.choose("raise")
    assert scene.decision is not None


def test_cannot_sit_without_enough_chips() -> None:
    app = App(AppOptions(mute=True))
    app.casino.wallet.debit(app.casino.balance - dollars(100))
    app.scenes.switch(app.make_scene("poker"))
    scene = app.scenes.top
    assert not scene.btn_sit.enabled
    scene.sit_down()
    assert not scene.room.seated
    pygame.quit()
