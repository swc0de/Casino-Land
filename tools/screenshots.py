"""Regenerate the README screenshots: ``python tools/screenshots.py [OUT_DIR]``.

Runs headless (SDL dummy drivers), stages each screen with a fixed seed and forced
results so the images are repeatable, and writes JPEGs to ``docs/screenshots``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from neon_royale.core import roulette as r
from neon_royale.core.blackjack import Action
from neon_royale.core.cards import Shoe, cards
from neon_royale.ui.app import App, AppOptions


def run(app: App, frames: int, each=None) -> None:
    for _ in range(frames):
        if each is not None:
            each()
        for event in pygame.event.get():
            app._handle_event(event)
        app.scenes.update(1 / 60)
        app.scenes.draw(app.screen)


def until(app: App, condition, limit: int = 60 * 60, each=None) -> None:
    for _ in range(limit):
        if condition():
            return
        run(app, 1, each)
    raise RuntimeError("screen never reached the expected state")


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    app = App(AppOptions(mute=True, seed=3))

    def shot(name: str) -> None:
        pygame.image.save(app.screen, out / f"{name}.jpg")
        print("wrote", out / f"{name}.jpg")

    app.scenes.switch(app.make_scene("title"), fade=0)
    run(app, 60 * 4)
    shot("title")

    app.scenes.switch(app.make_scene("lobby"), fade=0)
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(640, 360), rel=(0, 0), buttons=(0, 0, 0))
    )
    run(app, 40)
    shot("lobby")

    app.scenes.switch(app.make_scene("roulette"), fade=0)
    roulette = app.scenes.top
    for chip, bet in ((1, r.straight(17)), (1, r.split(17, 20)), (1, r.corner(13)),
                      (2, r.red()), (2, r.dozen(1)), (3, r.column(1))):  # fmt: skip
        roulette.rack.select(chip)
        roulette.place(bet)
    run(app, 30)
    spin = roulette.table.spin
    roulette.table.spin = lambda number=None: spin(17)
    roulette.spin()
    until(app, lambda: roulette.dolly is not None and roulette.ghosts is not None)
    run(app, 70)
    shot("roulette")

    app.scenes.switch(app.make_scene("blackjack"), fade=0)
    blackjack = app.scenes.top
    blackjack.table.shoe = Shoe.stacked(cards("8h 9s 8d 7c 3s Kd 5c Ts 2h 9h"))
    blackjack.rack.select(2)
    blackjack.add_chip()
    blackjack.add_chip()
    blackjack.deal()
    until(app, lambda: blackjack.mode == "player")
    blackjack.act(Action.SPLIT)
    until(app, lambda: blackjack.mode == "player")
    blackjack.act(Action.DOUBLE)
    until(app, lambda: blackjack.mode == "player")
    blackjack.act(Action.STAND)
    until(app, lambda: bool(blackjack.labels) and len(blackjack.labels) == 2)
    run(app, 30)
    shot("blackjack")

    app.scenes.switch(app.make_scene("poker"), fade=0)
    poker = app.scenes.top
    poker.sit_down()

    def call() -> None:
        if poker.mode == "human":
            poker.choose("call")

    until(app, lambda: any(v.hand_desc for v in poker.seats) and poker.banner.active,
          limit=60 * 240, each=call)  # fmt: skip
    run(app, 50)
    shot("poker")
    pygame.quit()


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/screenshots"))
