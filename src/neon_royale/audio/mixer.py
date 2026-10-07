"""The sound bank: turns synthesised samples into pygame sounds and plays them."""

from __future__ import annotations

import math
import queue
import random
import threading
import time
from typing import TYPE_CHECKING

import numpy as np
import pygame

from . import synth

if TYPE_CHECKING:
    from ..core.save import Settings

LOOP_CHANNELS = 4  # reserved for wheel, ball and ambience loops

# Quick, frequently used sounds first so they are ready by the time anyone clicks.
_ORDER = (
    "ui_hover",
    "ui_click",
    "neon_buzz",
    "whoosh",
    "chip_clack",
    "chip_stack",
    "card_deal",
    "card_flip",
    "ui_error",
    "ball_tick",
    "ball_drop",
    "win",
    "lose",
    "push",
    "blackjack",
    "shuffle",
    "chip_cascade",
    "ball_roll",
    "wheel_spin",
    "win_big",
    "ambience",
)

# Minimum gap between repeats of the same sound, so bursts don't pile up into noise.
_MIN_GAP = {"ui_hover": 0.05, "neon_buzz": 0.15, "chip_clack": 0.03, "ball_tick": 0.02}

_DTYPES = {8: np.uint8, -8: np.int8, 16: np.uint16, -16: np.int16, 32: np.float32, -32: np.int32}


def to_mixer_array(samples: np.ndarray, size: int, channels: int) -> np.ndarray:
    """Convert mono float samples to the mixer's sample format and channel count."""
    dtype = _DTYPES.get(size, np.int16)
    clipped = np.clip(samples, -1.0, 1.0)
    if dtype is np.float32:
        data = clipped.astype(np.float32)
    elif dtype in (np.uint8, np.uint16):
        bits = 8 if dtype is np.uint8 else 16
        half = 2 ** (bits - 1)
        data = (clipped * (half - 1) + half).astype(dtype)
    else:
        info = np.iinfo(dtype)
        data = (clipped * info.max).astype(dtype)
    if channels > 1:
        data = np.repeat(data[:, None], channels, axis=1)
    return np.ascontiguousarray(data)


class SoundBank:
    def __init__(self, enabled: bool, settings: Settings, seed: int = 7) -> None:
        self.settings = settings
        self.enabled = enabled and bool(pygame.mixer.get_init())
        self.sounds: dict[str, list[pygame.mixer.Sound]] = {}
        self._loops: dict[str, tuple[int, float]] = {}  # name -> (channel index, volume)
        self._last_played: dict[str, float] = {}
        self._rng = random.Random(seed)
        self._done = queue.Queue[tuple[str, list[np.ndarray]] | None]()
        self._thread: threading.Thread | None = None
        self._pending = len(_ORDER)
        if self.enabled:
            freq, self._size, self._channels = pygame.mixer.get_init()
            self._freq = freq
            pygame.mixer.set_reserved(LOOP_CHANNELS)
            self._thread = threading.Thread(
                target=self._generate, args=(seed,), name="sound-synth", daemon=True
            )
            self._thread.start()

    # -- loading ------------------------------------------------------------------------

    def _generate(self, seed: int) -> None:
        for name in _ORDER:
            variants = [
                synth.generate(name, seed + v, self._freq)
                for v in range(synth.VARIANTS.get(name, 1))
            ]
            self._done.put((name, variants))
        self._done.put(None)

    def update(self) -> None:
        """Adopt freshly generated sounds. Call once per frame from the main thread."""
        if not self.enabled:
            return
        while True:
            try:
                item = self._done.get_nowait()
            except queue.Empty:
                return
            if item is None:
                continue
            name, variants = item
            self.sounds[name] = [
                pygame.sndarray.make_sound(to_mixer_array(v, self._size, self._channels))
                for v in variants
            ]
            self._pending -= 1

    @property
    def ready(self) -> bool:
        return not self.enabled or self._pending == 0

    def wait_until_ready(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while not self.ready and time.monotonic() < deadline:
            self.update()
            time.sleep(0.005)
        return self.ready

    # -- volumes ------------------------------------------------------------------------

    def _sfx_gain(self) -> float:
        return self.settings.master_volume * self.settings.sfx_volume

    def _loop_gain(self, name: str) -> float:
        group = self.settings.ambience_volume if name == "ambience" else self.settings.sfx_volume
        return self.settings.master_volume * group

    def apply_volumes(self) -> None:
        """Re-apply settings to running loops after the player changes a slider."""
        for name, (index, volume) in self._loops.items():
            pygame.mixer.Channel(index).set_volume(volume * self._loop_gain(name))

    # -- playback -----------------------------------------------------------------------

    def play(self, name: str, volume: float = 1.0, pan: float = 0.0) -> None:
        """Play a one-shot. ``pan`` runs from -1 (left) to 1 (right)."""
        if not self.enabled or name not in self.sounds:
            return
        now = time.monotonic()
        gap = _MIN_GAP.get(name, 0.0)
        if gap and now - self._last_played.get(name, -1.0) < gap:
            return
        self._last_played[name] = now
        sound = self._rng.choice(self.sounds[name])
        channel = sound.play()
        if channel is None:
            return
        gain = max(0.0, min(1.0, volume * self._sfx_gain()))
        angle = (max(-1.0, min(1.0, pan)) + 1) * math.pi / 4
        channel.set_volume(
            gain * math.cos(angle) * math.sqrt(2), gain * math.sin(angle) * math.sqrt(2)
        )

    def loop(self, name: str, volume: float = 1.0, fade_ms: int = 500) -> None:
        """Start (or re-level) a looping sound on one of the reserved channels."""
        if not self.enabled or name not in self.sounds:
            return
        if name in self._loops:
            index, _ = self._loops[name]
            self._loops[name] = (index, volume)
            channel = pygame.mixer.Channel(index)
            channel.set_volume(volume * self._loop_gain(name))
            if channel.get_busy():
                return
        else:
            taken = {i for i, _ in self._loops.values()}
            free = [i for i in range(LOOP_CHANNELS) if i not in taken]
            if not free:
                return
            index = free[0]
            self._loops[name] = (index, volume)
            channel = pygame.mixer.Channel(index)
        channel.play(self.sounds[name][0], loops=-1, fade_ms=fade_ms)
        channel.set_volume(volume * self._loop_gain(name))

    def is_looping(self, name: str) -> bool:
        return name in self._loops

    def set_loop_volume(self, name: str, volume: float) -> None:
        if name in self._loops:
            index, _ = self._loops[name]
            self._loops[name] = (index, volume)
            pygame.mixer.Channel(index).set_volume(max(0.0, volume) * self._loop_gain(name))

    def stop_loop(self, name: str, fade_ms: int = 400) -> None:
        if name in self._loops:
            index, _ = self._loops.pop(name)
            channel = pygame.mixer.Channel(index)
            if fade_ms > 0:
                channel.fadeout(fade_ms)
            else:
                channel.stop()

    def stop_all(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
        self._loops.clear()
