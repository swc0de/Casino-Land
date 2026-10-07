"""Procedural sound effects synthesised with numpy.

Every sound in the game is generated here at start-up, so the project needs no audio
files. Each recipe returns mono float32 samples in [-1, 1]. Filtering is done in the
frequency domain (one FFT per sound), which keeps generation fast without SciPy.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

SAMPLE_RATE = 44100

Recipe = Callable[[np.random.Generator, int], np.ndarray]


# -- building blocks ------------------------------------------------------------------


def _n(seconds: float, sr: int) -> int:
    return max(1, round(seconds * sr))


def _time(seconds: float, sr: int) -> np.ndarray:
    return np.arange(_n(seconds, sr)) / sr


def _decay(seconds: float, tau: float, sr: int) -> np.ndarray:
    return np.exp(-_time(seconds, sr) / tau)


def _fade(sig: np.ndarray, sr: int, fade_in: float = 0.002, fade_out: float = 0.01) -> np.ndarray:
    out = sig.copy()
    a, b = min(len(out), _n(fade_in, sr)), min(len(out), _n(fade_out, sr))
    if a > 1:
        out[:a] *= np.linspace(0.0, 1.0, a)
    if b > 1:
        out[-b:] *= np.linspace(1.0, 0.0, b)
    return out


def _band(sig: np.ndarray, sr: int, low: float, high: float, soft: float = 0.25) -> np.ndarray:
    """Band-pass with raised-cosine shoulders (``soft`` is the shoulder width in octaves)."""
    spectrum = np.fft.rfft(sig)
    freqs = np.fft.rfftfreq(len(sig), 1 / sr)
    gain = np.ones_like(freqs)
    with np.errstate(divide="ignore"):
        octaves = np.log2(np.maximum(freqs, 1e-6))
    if low > 0:
        lo = np.log2(low)
        rise = np.clip((octaves - (lo - soft)) / soft, 0, 1)
        gain *= 0.5 - 0.5 * np.cos(np.pi * rise)
    if high < sr / 2:
        hi = np.log2(high)
        fall = np.clip(((hi + soft) - octaves) / soft, 0, 1)
        gain *= 0.5 - 0.5 * np.cos(np.pi * fall)
    return np.fft.irfft(spectrum * gain, n=len(sig))


def _noise(rng: np.random.Generator, seconds: float, sr: int) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, _n(seconds, sr))


def _brown(rng: np.random.Generator, seconds: float, sr: int) -> np.ndarray:
    walk = np.cumsum(rng.normal(0, 1, _n(seconds, sr)))
    walk -= np.linspace(walk[0], walk[-1], len(walk))  # remove drift so it loops cleanly
    return walk / (np.max(np.abs(walk)) + 1e-9)


def _resonance(freq: float, tau: float, seconds: float, sr: int, phase: float = 0.0) -> np.ndarray:
    t = _time(seconds, sr)
    return np.sin(2 * np.pi * freq * t + phase) * np.exp(-t / tau)


def _bell(
    freq: float, seconds: float, sr: int, brightness: float = 2.5, tau: float = 0.35
) -> np.ndarray:
    """FM bell: inharmonic modulator whose index decays faster than the tone."""
    t = _time(seconds, sr)
    index = brightness * np.exp(-t / (tau * 0.4))
    carrier = np.sin(2 * np.pi * freq * t + index * np.sin(2 * np.pi * freq * 1.41 * t))
    attack = np.clip(t / 0.003, 0, 1)
    return carrier * np.exp(-t / tau) * attack


def _brassy(freq: float, seconds: float, sr: int) -> np.ndarray:
    """A bright, slightly detuned saw-ish tone for fanfares."""
    t = _time(seconds, sr)
    tone = np.zeros_like(t)
    for detune in (0.997, 1.0, 1.004):
        for h in range(1, 9):
            tone += np.sin(2 * np.pi * freq * detune * h * t) / h
    env = np.clip(t / 0.02, 0, 1) * np.exp(-t / (seconds * 0.55))
    return tone * env / 6


def _mix_at(dst: np.ndarray, src: np.ndarray, start: float, sr: int, gain: float = 1.0) -> None:
    i = _n(start, sr) if start > 0 else 0
    if i >= len(dst):
        return
    end = min(len(dst), i + len(src))
    dst[i:end] += src[: end - i] * gain


def _normalise(sig: np.ndarray, peak: float = 0.9) -> np.ndarray:
    top = float(np.max(np.abs(sig))) if len(sig) else 0.0
    if top < 1e-9:
        return sig.astype(np.float32)
    return (sig * (peak / top)).astype(np.float32)


def _loopable(sig: np.ndarray, sr: int, crossfade: float = 0.25) -> np.ndarray:
    """Fold the tail over the head with an equal-power crossfade so the loop is seamless."""
    n = _n(crossfade, sr)
    body = sig[:-n].copy()
    k = np.linspace(0, np.pi / 2, n)
    body[:n] = sig[:n] * np.sin(k) + sig[-n:] * np.cos(k)
    return body


# -- recipes --------------------------------------------------------------------------


def _impact(rng: np.random.Generator, sr: int, brightness: float = 1.0) -> np.ndarray:
    """A single clay-chip impact: noisy click plus ringing ceramic partials."""
    dur = 0.09
    click = _band(_noise(rng, dur, sr), sr, 2200 * brightness, 9500) * _decay(dur, 0.004, sr)
    ring = np.zeros(_n(dur, sr))
    for base, amp in ((3150, 0.5), (4700, 0.35), (6900, 0.22)):
        f = base * brightness * rng.uniform(0.94, 1.06)
        ring += amp * _resonance(f, rng.uniform(0.012, 0.022), dur, sr, rng.uniform(0, 6.28))
    return click * 1.4 + ring


def chip_clack(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    out = np.zeros(_n(0.14, sr))
    _mix_at(out, _impact(rng, sr), 0.0, sr)
    _mix_at(out, _impact(rng, sr, 1.05), rng.uniform(0.008, 0.02), sr, 0.55)
    return _normalise(_fade(out, sr), 0.8)


def chip_stack(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    out = np.zeros(_n(0.42, sr))
    t = 0.0
    for i in range(rng.integers(4, 7)):
        _mix_at(out, _impact(rng, sr, rng.uniform(0.95, 1.1)), t, sr, 1.0 - i * 0.12)
        t += rng.uniform(0.028, 0.055)
    return _normalise(_fade(out, sr), 0.8)


def chip_cascade(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """A dealer pushing a big payout: lots of chips landing."""
    out = np.zeros(_n(1.0, sr))
    for _ in range(28):
        t = rng.beta(1.6, 2.6) * 0.8
        _mix_at(out, _impact(rng, sr, rng.uniform(0.9, 1.15)), t, sr, rng.uniform(0.35, 1.0))
    return _normalise(_fade(out, sr, fade_out=0.05), 0.85)


def card_deal(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    dur = 0.16
    t = _time(dur, sr)
    swish = _band(_noise(rng, dur, sr), sr, 1400, 7500)
    env = np.clip(t / 0.06, 0, 1) ** 2 * np.exp(-np.clip(t - 0.06, 0, None) / 0.03)
    out = swish * env * 0.6
    snap = _band(_noise(rng, 0.02, sr), sr, 2500, 11000) * _decay(0.02, 0.003, sr)
    _mix_at(out, snap, 0.085, sr, 1.0)
    return _normalise(_fade(out, sr), 0.7)


def card_flip(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    dur = 0.07
    snap = _band(_noise(rng, dur, sr), sr, 1800, 9000) * _decay(dur, 0.007, sr)
    thump = _resonance(170, 0.012, dur, sr) * 0.5
    return _normalise(_fade(snap + thump, sr), 0.7)


def shuffle(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """A riffle shuffle: a rush of tiny card clicks, then the bridge."""
    out = np.zeros(_n(1.15, sr))
    clicks = 70
    for i in range(clicks):
        x = i / clicks
        t = 0.05 + 0.75 * (x - 0.15 * np.sin(np.pi * x))
        click = _band(_noise(rng, 0.006, sr), sr, 2000, 10000) * _decay(0.006, 0.0012, sr)
        _mix_at(out, click, t, sr, rng.uniform(0.4, 1.0))
    bridge = _band(_noise(rng, 0.3, sr), sr, 600, 5000)
    bt = _time(0.3, sr)
    _mix_at(out, bridge * np.sin(np.pi * bt / 0.3) ** 2 * 0.5, 0.82, sr)
    return _normalise(_fade(out, sr), 0.65)


def wheel_spin(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Loop: the low rumble of a spinning roulette wheel."""
    dur = 2.25
    t = _time(dur, sr)
    rumble = _band(_brown(rng, dur, sr), sr, 40, 260) * 2.5
    body = _band(_noise(rng, dur, sr), sr, 300, 1100) * 0.25
    wobble = 0.8 + 0.2 * np.sin(2 * np.pi * (1 / 0.75) * t)  # 3 wobbles per loop
    return _normalise(_loopable((rumble + body) * wobble, sr), 0.55)


def ball_roll(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Loop: the ball whirring round the wheel's track."""
    dur = 1.75
    t = _time(dur, sr)
    whirr = _band(_noise(rng, dur, sr), sr, 1100, 3800)
    flutter = 0.75 + 0.25 * np.sin(2 * np.pi * 24 * t)
    return _normalise(_loopable(whirr * flutter, sr), 0.5)


def ball_tick(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """The ball clipping a fret or deflector."""
    dur = 0.05
    click = _band(_noise(rng, dur, sr), sr, 3000, 11000) * _decay(dur, 0.002, sr)
    ring = _resonance(rng.uniform(4800, 5600), 0.008, dur, sr) * 0.6
    return _normalise(_fade(click + ring, sr), 0.6)


def ball_drop(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """The ball dropping into a pocket and settling."""
    out = np.zeros(_n(0.6, sr))
    thump = _resonance(150, 0.03, 0.15, sr) + _band(_noise(rng, 0.15, sr), sr, 400, 4000) * _decay(
        0.15, 0.01, sr
    )
    _mix_at(out, thump, 0.0, sr)
    for t, gain in ((0.11, 0.55), (0.19, 0.35), (0.245, 0.2), (0.28, 0.1)):
        _mix_at(out, ball_tick(rng, sr), t, sr, gain)
    return _normalise(_fade(out, sr, fade_out=0.05), 0.75)


C5, E5, G5, C6, E6, G6, C7 = 523.25, 659.26, 783.99, 1046.5, 1318.5, 1568.0, 2093.0


def win(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    out = np.zeros(_n(1.0, sr))
    for i, f in enumerate((C6, E6, G6, C7)):
        _mix_at(out, _bell(f, 0.8, sr, 1.8, 0.3), i * 0.075, sr, 0.6)
    for f in (C6, E6, G6):
        _mix_at(out, _bell(f, 0.7, sr, 1.0, 0.35), 0.3, sr, 0.25)
    return _normalise(_fade(out, sr, fade_out=0.08), 0.75)


def win_big(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    out = np.zeros(_n(2.4, sr))
    for start in (0.0, 0.16):
        for f in (C5, E5, G5):
            _mix_at(out, _brassy(f, 0.32, sr), start, sr, 0.5)
    _mix_at(out, np.concatenate([_brassy(f, 0.9, sr) for f in (C6,)]), 0.34, sr, 0.5)
    for f in (C5, E5, G5):
        _mix_at(out, _brassy(f, 1.1, sr), 0.34, sr, 0.45)
    ladder = (C6, E6, G6, C7, G6, C7, E6 * 2, G6 * 2)
    for i, f in enumerate(ladder * 2):
        _mix_at(out, _bell(f, 0.5, sr, 2.2, 0.18), 0.4 + i * 0.06, sr, 0.22)
    shimmer = _band(_noise(rng, 1.6, sr), sr, 6000, 14000) * _decay(1.6, 0.5, sr) * 0.12
    _mix_at(out, shimmer, 0.35, sr)
    return _normalise(_fade(out, sr, fade_out=0.3), 0.85)


def blackjack(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """A sparkly three-bell sting for a natural 21."""
    out = np.zeros(_n(1.2, sr))
    for i, f in enumerate((G6, C7, E6 * 2)):
        _mix_at(out, _bell(f, 0.9, sr, 2.8, 0.4), i * 0.11, sr, 0.5)
    shimmer = _band(_noise(rng, 0.9, sr), sr, 7000, 15000) * _decay(0.9, 0.3, sr) * 0.1
    _mix_at(out, shimmer, 0.2, sr)
    return _normalise(_fade(out, sr, fade_out=0.15), 0.8)


def lose(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Soft and brief: a gentle falling pair, nothing mocking."""
    out = np.zeros(_n(0.55, sr))
    for i, f in enumerate((392.0, 293.66)):
        t = _time(0.3, sr)
        tone = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
        _mix_at(out, tone * np.clip(t / 0.01, 0, 1) * np.exp(-t / 0.12), i * 0.14, sr, 0.5)
    return _normalise(_fade(out, sr), 0.45)


def push(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    return _normalise(_fade(_bell(880.0, 0.5, sr, 1.0, 0.18), sr), 0.45)


def ui_hover(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = _time(0.035, sr)
    blip = np.sin(2 * np.pi * (2600 + 900 * t / t[-1]) * t) * np.exp(-t / 0.008)
    return _normalise(_fade(blip, sr, 0.001, 0.005), 0.3)


def ui_click(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    dur = 0.06
    click = _band(_noise(rng, dur, sr), sr, 1500, 8000) * _decay(dur, 0.003, sr)
    tone = _resonance(1250, 0.015, dur, sr) * 0.7
    return _normalise(_fade(click + tone, sr), 0.5)


def ui_error(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    out = np.zeros(_n(0.24, sr))
    t = _time(0.08, sr)
    buzz = np.sign(np.sin(2 * np.pi * 140 * t)) * 0.5 + np.sin(2 * np.pi * 280 * t) * 0.3
    buzz = _band(buzz, sr, 100, 2000) * np.exp(-t / 0.05)
    _mix_at(out, buzz, 0.0, sr)
    _mix_at(out, buzz, 0.12, sr)
    return _normalise(_fade(out, sr), 0.4)


def neon_buzz(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """The crackle and hum of a neon tube striking."""
    dur = 0.3
    t = _time(dur, sr)
    hum = sum(np.sin(2 * np.pi * 120 * h * t) / h for h in range(1, 7))
    crackle = _band(_noise(rng, dur, sr), sr, 2000, 9000) * (rng.random(len(t)) < 0.03)
    env = np.clip(t / 0.01, 0, 1) * np.exp(-t / 0.09)
    return _normalise(_fade((hum * 0.6 + crackle * 2) * env, sr), 0.35)


def whoosh(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Screen-transition swoosh."""
    dur = 0.45
    t = _time(dur, sr)
    air = _band(_noise(rng, dur, sr), sr, 500, 6000)
    env = np.sin(np.pi * t / dur) ** 2
    return _normalise(_fade(air * env, sr), 0.35)


def ambience(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Loop: a busy casino floor heard from the lobby: murmur, distant chimes, a low hum."""
    dur = 16.0
    t = _time(dur, sr)
    murmur = _band(_brown(rng, dur, sr), sr, 90, 700) * 1.6
    voices = _band(_noise(rng, dur, sr), sr, 300, 1400)
    swells = np.zeros_like(t)
    for _ in range(18):
        centre, width = rng.uniform(0, dur), rng.uniform(0.4, 1.4)
        swells += np.exp(-(((t - centre) / width) ** 2)) * rng.uniform(0.2, 0.6)
    room = murmur + voices * (0.12 + swells * 0.25)
    hum = 0.04 * np.sin(2 * np.pi * 60 * t) + 0.02 * np.sin(2 * np.pi * 120 * t)
    out = room + hum
    pentatonic = (C6, 1174.7, E6, G6, 1760.0, C7)
    for _ in range(9):
        start = rng.uniform(0.2, dur - 1.5)
        for k in range(rng.integers(2, 5)):
            f = float(rng.choice(pentatonic))
            _mix_at(out, _bell(f, 1.2, sr, 1.2, 0.3), start + k * 0.09, sr, 0.04)
    return _normalise(_loopable(out, sr, 1.0), 0.5)


RECIPES: dict[str, Recipe] = {
    "chip_clack": chip_clack,
    "chip_stack": chip_stack,
    "chip_cascade": chip_cascade,
    "card_deal": card_deal,
    "card_flip": card_flip,
    "shuffle": shuffle,
    "wheel_spin": wheel_spin,
    "ball_roll": ball_roll,
    "ball_tick": ball_tick,
    "ball_drop": ball_drop,
    "win": win,
    "win_big": win_big,
    "blackjack": blackjack,
    "lose": lose,
    "push": push,
    "ui_hover": ui_hover,
    "ui_click": ui_click,
    "ui_error": ui_error,
    "neon_buzz": neon_buzz,
    "whoosh": whoosh,
    "ambience": ambience,
}

#: Sounds that are played as seamless loops.
LOOPS = frozenset({"wheel_spin", "ball_roll", "ambience"})

#: How many random variations to pre-generate so repeats don't sound robotic.
VARIANTS: dict[str, int] = {
    "chip_clack": 4,
    "chip_stack": 3,
    "card_deal": 3,
    "card_flip": 3,
    "ball_tick": 4,
}


def generate(name: str, seed: int = 0, sr: int = SAMPLE_RATE) -> np.ndarray:
    return RECIPES[name](np.random.default_rng(seed), sr)
