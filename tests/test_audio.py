from __future__ import annotations

import numpy as np
import pygame
import pytest

from neon_royale.audio import mixer, synth
from neon_royale.audio.mixer import SoundBank, to_mixer_array
from neon_royale.core.save import Settings

SR = 22050  # half rate keeps the test quick; recipes must work at any rate


@pytest.mark.parametrize("name", sorted(synth.RECIPES))
def test_recipe_produces_clean_audio(name: str) -> None:
    samples = synth.generate(name, seed=3, sr=SR)
    assert samples.dtype == np.float32
    assert samples.ndim == 1
    assert 0.02 * SR < len(samples) < 20 * SR
    assert np.isfinite(samples).all()
    peak = float(np.max(np.abs(samples)))
    assert 0.1 < peak <= 1.0, "audible but never clipping"


def test_recipes_are_deterministic_per_seed() -> None:
    a = synth.generate("chip_clack", seed=1, sr=SR)
    b = synth.generate("chip_clack", seed=1, sr=SR)
    c = synth.generate("chip_clack", seed=2, sr=SR)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


@pytest.mark.parametrize("name", sorted(synth.LOOPS))
def test_loops_join_without_a_click(name: str) -> None:
    samples = synth.generate(name, seed=0, sr=SR)
    typical_step = float(np.median(np.abs(np.diff(samples))))
    seam = abs(float(samples[0]) - float(samples[-1]))
    assert seam < max(0.05, typical_step * 12)


def test_every_recipe_is_scheduled_for_loading() -> None:
    assert set(mixer._ORDER) == set(synth.RECIPES)
    assert len(mixer._ORDER) == len(set(mixer._ORDER))


@pytest.mark.parametrize(
    ("size", "dtype", "top"),
    [(-16, np.int16, 32767), (32, np.float32, 1.0), (16, np.uint16, 65535)],
)
def test_to_mixer_array_formats(size: int, dtype: type, top: float) -> None:
    out = to_mixer_array(np.array([0.0, 1.0, 2.0, -1.0]), size, 2)
    assert out.dtype == dtype
    assert out.shape == (4, 2)
    assert out[1, 0] == pytest.approx(top, rel=1e-3)
    assert out[2, 1] == out[1, 1], "values beyond full scale are clipped"


def test_sound_bank_loads_and_plays_with_dummy_driver() -> None:
    pygame.mixer.init(44100, -16, 2, 512)
    try:
        bank = SoundBank(True, Settings())
        assert bank.wait_until_ready(timeout=30)
        assert set(bank.sounds) == set(synth.RECIPES)
        bank.play("chip_clack", pan=-0.5)
        bank.play("chip_clack")  # throttled repeat must be harmless
        bank.loop("ambience")
        assert bank.is_looping("ambience")
        bank.set_loop_volume("ambience", 0.3)
        bank.apply_volumes()
        bank.stop_loop("ambience", fade_ms=0)
        assert not bank.is_looping("ambience")
        bank.stop_all()
    finally:
        pygame.mixer.quit()


def test_disabled_sound_bank_is_a_no_op() -> None:
    bank = SoundBank(False, Settings())
    assert bank.ready
    bank.play("win")
    bank.loop("ambience")
    assert not bank.is_looping("ambience")
