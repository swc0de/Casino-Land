"""Roulette presentation: layout hit-testing, ball motion and a full scene round."""

from __future__ import annotations

import math
import random

import pygame
import pytest

from neon_royale.core import roulette as r
from neon_royale.core.money import dollars
from neon_royale.ui.app import App, AppOptions
from neon_royale.ui.fx.spin import WheelSpin
from neon_royale.ui.roulette_board import BoardGeometry

GEOM = BoardGeometry(left=462, top=150)


@pytest.mark.parametrize("bet", r.all_bets(), ids=lambda b: b.label)
def test_every_bet_spot_hits_its_own_bet(bet: r.Bet) -> None:
    x, y = GEOM.spot(bet)
    assert GEOM.bet_at((round(x), round(y))) == bet


def test_points_around_17() -> None:
    cell = GEOM.cell_rect(17)
    assert GEOM.bet_at(cell.center) == r.straight(17)
    assert GEOM.bet_at(cell.midright) == r.split(17, 20)
    assert GEOM.bet_at(cell.midleft) == r.split(14, 17)
    assert GEOM.bet_at(cell.midtop) == r.split(17, 18)
    assert GEOM.bet_at(cell.midbottom) == r.split(16, 17)
    assert GEOM.bet_at(cell.topright) == r.corner(17)
    assert GEOM.bet_at(cell.bottomleft) == r.corner(13)


def test_zero_edge_bets() -> None:
    gl, top, ch = GEOM.grid_left, GEOM.top, GEOM.cell_h
    assert GEOM.bet_at(GEOM.zero_rect.center) == r.straight(0)
    assert GEOM.bet_at((gl, top + ch // 2)) == r.split(0, 3)
    assert GEOM.bet_at((gl, top + ch)) == r.trio(3)
    assert GEOM.bet_at((gl, top + 2 * ch)) == r.trio(1)
    assert GEOM.bet_at((gl, top + 3 * ch)) == r.first_four()


def test_street_and_outside_boxes() -> None:
    bottom = GEOM.top + 3 * GEOM.cell_h
    assert GEOM.bet_at((GEOM.cell_rect(1).centerx, bottom)) == r.street(0)
    assert GEOM.bet_at((GEOM.cell_rect(1).right, bottom)) == r.six_line(0)
    assert GEOM.bet_at(GEOM.dozen_rect(2).center) == r.dozen(2)
    assert GEOM.bet_at(GEOM.column_rect(0).center) == r.column(0)
    assert GEOM.bet_at((10, 10)) is None


@pytest.mark.parametrize("index", [0, 5, 18, 36])
def test_ball_lands_in_the_chosen_pocket(index: int) -> None:
    spin = WheelSpin(random.Random(index))
    spin.launch(index, r.POCKETS, duration=4.0)
    events: list[str] = []
    for _ in range(4 * 60 + 5):
        events += spin.update(1 / 60)
    assert not spin.spinning
    assert events[0] == "drop" and events[-1] == "settled"
    assert events.count("tick") >= 3
    relative = (spin.ball_angle() - spin.wheel_angle) % math.tau
    expected = index * math.tau / r.POCKETS
    assert math.isclose(relative, expected, abs_tol=1e-9)
    assert spin.ball_height() == 0.0
    # The ball keeps riding in its pocket as the wheel turns.
    spin.update(1.0)
    assert math.isclose((spin.ball_angle() - spin.wheel_angle) % math.tau, expected, abs_tol=1e-9)


def test_ball_travels_anticlockwise_on_the_track_first() -> None:
    spin = WheelSpin(random.Random(1))
    spin.launch(10, r.POCKETS)
    a0 = spin.ball_angle()
    spin.update(0.05)
    assert spin.ball_height() == 1.0
    assert (spin.ball_angle() - a0) % math.tau > math.pi, "moving anticlockwise"


def _run_until_idle(app: App, scene, seconds: float = 20.0) -> None:
    for _ in range(round(seconds * 60)):
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)
        if not scene.busy:
            return
    raise AssertionError("round never finished")


def test_full_round_in_the_scene() -> None:
    app = App(AppOptions(mute=True, seed=4))
    app.settings.fast_animations = True
    app.scenes.switch(app.make_scene("roulette"))
    scene = app.scenes.top
    start = app.casino.balance

    scene.rack.select(1)  # $5
    scene.place(r.straight(17))
    scene.place(r.red())
    assert app.casino.balance == start - dollars(10)
    scene.place(r.straight(17))
    scene.undo()
    assert scene.table.total_bet == dollars(10)

    original = scene.table.spin
    scene.table.spin = lambda number=None: original(17)
    scene.spin()
    assert scene.busy
    scene.place(r.black())  # ignored while spinning
    assert scene.table.total_bet == dollars(10)
    _run_until_idle(app, scene)

    assert scene.table.history == [17]
    assert app.casino.balance == start - dollars(10) + dollars(180)
    assert app.casino.profile.stats["roulette"].rounds == 1
    assert scene.balance.target == app.casino.balance

    scene.rebet()
    assert scene.table.total_bet == dollars(10)
    scene.leave()
    assert app.casino.balance == start + dollars(170), "leaving refunds unspun bets"
    pygame.quit()


def test_scene_refuses_bad_actions_politely() -> None:
    app = App(AppOptions(mute=True))
    app.scenes.switch(app.make_scene("roulette"))
    scene = app.scenes.top
    scene.spin()
    assert not scene.busy
    assert scene.toast.items
    scene.rebet()
    scene.double()
    app.casino.wallet.debit(app.casino.balance)
    scene.place(r.red())
    assert scene.table.total_bet == 0
    pygame.quit()
