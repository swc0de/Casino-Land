"""Easing curves, tweens and a script runner for sequencing animations.

Game scenes turn engine events into animations ("deal this card, flip it, pay this
bet"). Writing those as generator scripts that ``yield`` what they wait for keeps a
long sequence readable::

    def deal(self):
        yield self.anim.to(card, "x", 400, 0.3, ease_out_cubic)
        yield 0.1                      # pause
        self.sound.play("card_flip")
        yield self.anim.to(card, "flip", 1.0, 0.2)

Nothing here imports pygame, so it is unit-tested directly.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Generator, Iterable
from typing import Any

Ease = Callable[[float], float]


# -- easing ---------------------------------------------------------------------------


def linear(t: float) -> float:
    return t


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) * (1 - t)


def ease_in_cubic(t: float) -> float:
    return t * t * t


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_quint(t: float) -> float:
    return 1 - (1 - t) ** 5


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_back(t: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_out_elastic(t: float) -> float:
    if t in (0.0, 1.0):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def ease_out_bounce(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _mix(a: Any, b: Any, k: float) -> Any:
    if isinstance(a, tuple):
        return tuple(x + (y - x) * k for x, y in zip(a, b, strict=True))
    return a + (b - a) * k


# -- tweens ---------------------------------------------------------------------------


class Tween:
    """Moves ``target.attr`` (a number or tuple of numbers) to ``end`` over ``duration``."""

    def __init__(
        self,
        target: Any,
        attr: str,
        end: Any,
        duration: float,
        ease: Ease = ease_out_cubic,
        delay: float = 0.0,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self.target = target
        self.attr = attr
        self.end = end
        self.duration = max(duration, 0.0)
        self.ease = ease
        self.delay = delay
        self.on_done = on_done
        self.elapsed = 0.0
        self.start: Any = None
        self.done = False

    def update(self, dt: float) -> None:
        if self.done:
            return
        if self.delay > 0:
            self.delay -= dt
            if self.delay > 0:
                return
            dt = -self.delay
            self.delay = 0.0
        if self.start is None:
            self.start = getattr(self.target, self.attr)
        self.elapsed += dt
        t = 1.0 if self.duration == 0 else min(1.0, self.elapsed / self.duration)
        setattr(self.target, self.attr, _mix(self.start, self.end, self.ease(t)))
        if t >= 1.0:
            setattr(self.target, self.attr, self.end)
            self.finish()

    def finish(self) -> None:
        if not self.done:
            self.done = True
            if self.on_done is not None:
                self.on_done()

    def cancel(self) -> None:
        self.done = True


class Animator:
    """Owns running tweens. A new tween on the same attribute replaces the old one."""

    def __init__(self) -> None:
        self._tweens: list[Tween] = []

    def to(
        self,
        target: Any,
        attr: str,
        end: Any,
        duration: float,
        ease: Ease = ease_out_cubic,
        delay: float = 0.0,
        on_done: Callable[[], None] | None = None,
    ) -> Tween:
        for tween in self._tweens:
            if tween.target is target and tween.attr == attr and not tween.done:
                tween.cancel()
        tween = Tween(target, attr, end, duration, ease, delay, on_done)
        self._tweens.append(tween)
        return tween

    def update(self, dt: float) -> None:
        for tween in list(self._tweens):
            tween.update(dt)
        self._tweens = [t for t in self._tweens if not t.done]

    def cancel_all(self, target: Any = None) -> None:
        for tween in self._tweens:
            if target is None or tween.target is target:
                tween.cancel()
        self._tweens = [t for t in self._tweens if not t.done]

    @property
    def busy(self) -> bool:
        return bool(self._tweens)


# -- scripts --------------------------------------------------------------------------

Script = Generator[Any, None, None]


class _Wait:
    def __init__(self, seconds: float) -> None:
        self.remaining = seconds

    def consume(self, dt: float) -> float:
        """Use up ``dt``; return whatever is left over once the wait has ended."""
        self.remaining -= dt
        return max(0.0, -self.remaining)

    @property
    def done(self) -> bool:
        return self.remaining <= 0


class _NextFrame:
    def __init__(self, director: Director) -> None:
        self.director = director
        self.frame = director.frame

    @property
    def done(self) -> bool:
        return self.director.frame > self.frame


class _All:
    def __init__(self, items: Iterable[Any]) -> None:
        self.items = list(items)
        for item in self.items:
            if not hasattr(item, "done"):
                raise TypeError(f"can only wait on things with a 'done' flag, not {item!r}")

    @property
    def done(self) -> bool:
        return all(item.done for item in self.items)


class ScriptHandle:
    def __init__(self, script: Script) -> None:
        self.script = script
        self.waiting: Any = None
        self.done = False


class Director:
    """Runs generator scripts. A script may yield:

    * a number: wait that many seconds;
    * anything with a ``done`` attribute (a Tween, another ScriptHandle): wait for it;
    * a list or tuple of those: wait for all of them;
    * ``None``: wait until the next frame.

    Use ``yield from other_script()`` to call a sub-sequence inline.
    """

    def __init__(self) -> None:
        self._running: list[ScriptHandle] = []
        self.frame = 0

    def run(self, script: Script) -> ScriptHandle:
        """Start ``script`` now; it runs up to its first wait before this returns."""
        handle = ScriptHandle(script)
        self._running.append(handle)
        self._advance(handle, 0.0)
        return handle

    @property
    def busy(self) -> bool:
        return any(not h.done for h in self._running)

    def cancel_all(self) -> None:
        for handle in self._running:
            handle.script.close()
            handle.done = True
        self._running.clear()

    def update(self, dt: float) -> None:
        self.frame += 1
        for handle in list(self._running):
            if not handle.done:
                self._advance(handle, dt)
        self._running = [h for h in self._running if not h.done]

    def _advance(self, handle: ScriptHandle, dt: float) -> None:
        while True:
            waiting = handle.waiting
            if isinstance(waiting, _Wait):
                dt = waiting.consume(dt)
                if not waiting.done:
                    return
            elif waiting is not None and not waiting.done:
                return
            try:
                value = next(handle.script)
            except StopIteration:
                handle.done = True
                return
            handle.waiting = self._normalise(value)

    def _normalise(self, value: Any) -> Any:
        if value is None:
            return _NextFrame(self)
        if isinstance(value, bool):
            raise TypeError("scripts cannot yield a bool")
        if isinstance(value, int | float):
            return _Wait(float(value))
        if isinstance(value, list | tuple):
            return _All(value)
        if not hasattr(value, "done"):
            raise TypeError(f"scripts can only wait on things with a 'done' flag, not {value!r}")
        return value
