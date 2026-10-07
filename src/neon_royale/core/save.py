"""Persistent profile: bankroll, lifetime stats and settings, stored as JSON."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .money import Cents, dollars

STARTING_BANKROLL: Cents = dollars(10_000)
COMP_AMOUNT: Cents = dollars(1_000)
SAVE_VERSION = 1


@dataclass
class Settings:
    master_volume: float = 0.8
    sfx_volume: float = 1.0
    ambience_volume: float = 0.5
    fullscreen: bool = False
    fast_animations: bool = False
    show_fps: bool = False


@dataclass
class GameStats:
    rounds: int = 0
    wagered: Cents = 0
    returned: Cents = 0
    biggest_win: Cents = 0

    @property
    def net(self) -> Cents:
        return self.returned - self.wagered

    def record(self, wagered: Cents, returned: Cents) -> None:
        self.rounds += 1
        self.wagered += wagered
        self.returned += returned
        self.biggest_win = max(self.biggest_win, returned - wagered)


@dataclass
class Profile:
    balance: Cents = STARTING_BANKROLL
    comps_received: int = 0
    stats: dict[str, GameStats] = field(
        default_factory=lambda: {
            "roulette": GameStats(),
            "blackjack": GameStats(),
            "poker": GameStats(),
        }
    )
    settings: Settings = field(default_factory=Settings)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": SAVE_VERSION,
            "balance": self.balance,
            "comps_received": self.comps_received,
            "stats": {name: asdict(s) for name, s in self.stats.items()},
            "settings": asdict(self.settings),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Profile:
        profile = cls()
        balance = data.get("balance", STARTING_BANKROLL)
        if isinstance(balance, int) and balance >= 0:
            profile.balance = balance
        comps = data.get("comps_received", 0)
        if isinstance(comps, int) and comps >= 0:
            profile.comps_received = comps
        for name, raw in (data.get("stats") or {}).items():
            if isinstance(raw, dict):
                profile.stats[name] = _load_dataclass(GameStats, raw)
        if isinstance(data.get("settings"), dict):
            profile.settings = _load_dataclass(Settings, data["settings"])
        return profile


def _load_dataclass(cls: type, raw: dict[str, Any]) -> Any:
    """Build ``cls`` from ``raw``, keeping defaults for missing or mistyped fields.

    Saves outlive code versions, so unknown keys are ignored and bad values fall
    back to defaults instead of crashing the game on launch.
    """
    obj = cls()
    for f in fields(cls):
        if f.name in raw:
            value = raw[f.name]
            default = getattr(obj, f.name)
            if isinstance(default, bool):
                ok = isinstance(value, bool)
            elif isinstance(default, float):
                ok = isinstance(value, int | float) and not isinstance(value, bool)
                value = float(value) if ok else value
            else:
                ok = isinstance(value, type(default)) and not isinstance(value, bool)
            if ok:
                setattr(obj, f.name, value)
    return obj


def default_save_path() -> Path:
    override = os.environ.get("NEON_ROYALE_SAVE")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "neon-royale" / "save.json"


def load_profile(path: Path) -> Profile:
    """Load a profile, starting fresh if the file is missing or unreadable.

    A corrupt save is kept alongside as ``*.corrupt`` rather than silently lost.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Profile()
    except OSError:
        return Profile()
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("save root is not an object")
        return Profile.from_json(data)
    except (ValueError, TypeError):
        with contextlib.suppress(OSError):
            path.replace(path.with_suffix(path.suffix + ".corrupt"))
        return Profile()


def save_profile(profile: Profile, path: Path) -> None:
    """Write atomically so a crash mid-write never corrupts the existing save."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(profile.to_json(), indent=2), encoding="utf-8")
    os.replace(tmp, path)
