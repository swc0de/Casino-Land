from __future__ import annotations

import json
from pathlib import Path

import pytest

from neon_royale.core.money import dollars
from neon_royale.core.save import (
    STARTING_BANKROLL,
    Profile,
    default_save_path,
    load_profile,
    save_profile,
)


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "save.json"
    profile = Profile(balance=dollars(1234.5))
    profile.settings.master_volume = 0.25
    profile.settings.fullscreen = True
    profile.stats["roulette"].record(dollars(10), dollars(360))
    save_profile(profile, path)

    loaded = load_profile(path)
    assert loaded.balance == dollars(1234.5)
    assert loaded.settings.master_volume == 0.25
    assert loaded.settings.fullscreen is True
    assert loaded.stats["roulette"].biggest_win == dollars(350)
    assert not path.with_suffix(".json.tmp").exists()


def test_missing_file_gives_fresh_profile(tmp_path: Path) -> None:
    assert load_profile(tmp_path / "nope.json").balance == STARTING_BANKROLL


def test_corrupt_file_is_set_aside(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_profile(path).balance == STARTING_BANKROLL
    assert (tmp_path / "save.json.corrupt").exists()
    assert not path.exists()


def test_bad_values_fall_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text(
        json.dumps(
            {
                "balance": -50,
                "settings": {"master_volume": "loud", "fullscreen": 1, "sfx_volume": 1},
                "stats": {"poker": {"rounds": "many", "wagered": 500}},
                "unknown": True,
            }
        ),
        encoding="utf-8",
    )
    profile = load_profile(path)
    assert profile.balance == STARTING_BANKROLL
    assert profile.settings.master_volume == 0.8
    assert profile.settings.fullscreen is False
    assert profile.settings.sfx_volume == 1.0
    assert profile.stats["poker"].rounds == 0
    assert profile.stats["poker"].wagered == 500


def test_save_path_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEON_ROYALE_SAVE", str(tmp_path / "x.json"))
    assert default_save_path() == tmp_path / "x.json"


def test_default_save_path_is_per_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEON_ROYALE_SAVE", raising=False)
    path = default_save_path()
    assert path.name == "save.json"
    assert path.parent.name == "neon-royale"
