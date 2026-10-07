"""Command-line entry point: ``python -m neon_royale`` or ``neon-royale``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neon-royale",
        description="Neon Royale Casino: Roulette, Blackjack and Texas Hold'em. Play money only.",
    )
    parser.add_argument(
        "--smoke",
        type=float,
        metavar="SECONDS",
        help="run for SECONDS then exit (launch check); doesn't touch your save unless --save",
    )
    parser.add_argument("--screenshot", type=Path, help="save the last frame to this PNG on exit")
    parser.add_argument("--scene", default="title", help="scene to start in (e.g. lobby)")
    parser.add_argument("--save", type=Path, help="profile file to use instead of the default")
    parser.add_argument("--seed", type=int, help="seed the random generator (repeatable deals)")
    parser.add_argument("--mute", action="store_true", help="start with audio disabled")
    screen = parser.add_mutually_exclusive_group()
    screen.add_argument("--fullscreen", action="store_true", default=None)
    screen.add_argument("--windowed", dest="fullscreen", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Imported here so `--help` works without initialising pygame.
    from .core.save import default_save_path
    from .ui.app import App, AppOptions

    save_path = args.save
    if save_path is None and args.smoke is None:
        save_path = default_save_path()

    options = AppOptions(
        smoke_seconds=args.smoke,
        screenshot=args.screenshot,
        start_scene=args.scene,
        save_path=save_path,
        seed=args.seed,
        fullscreen=args.fullscreen,
        mute=args.mute,
    )
    return App(options).run()


if __name__ == "__main__":
    sys.exit(main())
