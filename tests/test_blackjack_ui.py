"""Blackjack scene: full hands played through the UI layer, headless."""

from __future__ import annotations

import pygame
import pytest

from neon_royale.core.blackjack import Action, Phase
from neon_royale.core.cards import Shoe, cards
from neon_royale.core.money import dollars
from neon_royale.ui.app import App, AppOptions


@pytest.fixture
def scene():
    app = App(AppOptions(mute=True, seed=1))
    app.settings.fast_animations = True
    app.scenes.switch(app.make_scene("blackjack"))
    yield app.scenes.top
    pygame.quit()


def run_until(scene, mode: str | tuple[str, ...], seconds: float = 30.0) -> None:
    modes = (mode,) if isinstance(mode, str) else mode
    app = scene.app
    for _ in range(round(seconds * 60)):
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)
        if scene.mode in modes and not scene.director.busy:
            return
    raise AssertionError(f"stuck in {scene.mode}")


def bet(scene, amount: int) -> None:
    scene.bet_chips = []
    scene.rack.selected = scene.rack.denominations.index(amount)
    scene.add_chip()


def test_win_by_standing(scene) -> None:
    scene.table.shoe = Shoe.stacked(cards("Kh Ts Qd 8c"))
    start = scene.app.casino.balance
    bet(scene, dollars(25))
    assert scene.app.casino.balance == start, "nothing leaves the wallet until the deal"
    scene.deal()
    run_until(scene, "player")
    assert len(scene.hand_cards[0]) == 2 and len(scene.dealer_cards) == 2
    assert scene.dealer_cards[1].flip == 0.0, "hole card stays face down"
    scene.act(Action.STAND)
    run_until(scene, "betting")
    assert scene.app.casino.balance == start + dollars(25)
    assert scene.app.casino.profile.stats["blackjack"].rounds == 1
    assert scene.bet_chips == [dollars(25)], "the last bet is offered again"
    assert scene.table.phase is Phase.BETTING


def test_split_and_double_through_the_scene(scene) -> None:
    scene.table.shoe = Shoe.stacked(cards("8h 9s 8d 7c 3s Kd 5c Ts"))
    start = scene.app.casino.balance
    bet(scene, dollars(25))
    scene.deal()
    run_until(scene, "player")
    scene.act(Action.SPLIT)
    run_until(scene, "player")
    assert len(scene.hand_cards) == 2 and len(scene.stacks) == 2
    scene.act(Action.DOUBLE)
    run_until(scene, "player")
    assert scene.hand_cards[0][-1].angle == pytest.approx(90.0), "double card lies sideways"
    scene.act(Action.STAND)
    run_until(scene, "betting")
    assert scene.app.casino.balance == start + dollars(75)


def test_insurance_flow(scene) -> None:
    scene.table.shoe = Shoe.stacked(cards("Th As 9d Kc"))
    start = scene.app.casino.balance
    bet(scene, dollars(100))
    scene.deal()
    run_until(scene, "insurance")
    assert scene.btn_insure.visible
    scene.insure()
    run_until(scene, "betting")
    assert scene.app.casino.balance == start, "insurance covered the dealer blackjack"


def test_betting_guards(scene) -> None:
    scene.deal()
    assert scene.mode == "betting" and scene.toast.items
    scene.app.casino.wallet.debit(scene.app.casino.balance - dollars(30))
    bet(scene, dollars(25))
    for _ in range(10):
        scene.add_chip()  # the rack steps down to chips the player can still afford
    assert scene.pending_bet == dollars(30), "can't bet more than the bankroll"
    scene.remove_chip()
    assert scene.pending_bet == dollars(25)
    scene.hint()  # no-op outside a hand
    scene.leave()


def test_cannot_leave_mid_hand(scene) -> None:
    scene.table.shoe = Shoe.stacked(cards("Kh Ts Qd 8c"))
    bet(scene, dollars(5))
    scene.deal()
    run_until(scene, "player")
    scene.leave()
    assert scene.mode == "player"
    scene.hint()
    assert any("Basic strategy" in item[0] for item in scene.toast.items)
