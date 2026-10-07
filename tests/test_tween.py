from __future__ import annotations

import pytest

from neon_royale.ui.fx import tween
from neon_royale.ui.fx.tween import Animator, Director, Tween

EASINGS = [
    tween.linear,
    tween.ease_in_quad,
    tween.ease_out_quad,
    tween.ease_in_cubic,
    tween.ease_out_cubic,
    tween.ease_in_out_cubic,
    tween.ease_out_quint,
    tween.ease_in_out_sine,
    tween.ease_out_back,
    tween.ease_out_elastic,
    tween.ease_out_bounce,
]


@pytest.mark.parametrize("ease", EASINGS, ids=lambda f: f.__name__)
def test_easings_start_at_zero_and_end_at_one(ease) -> None:
    assert ease(0.0) == pytest.approx(0.0, abs=1e-9)
    assert ease(1.0) == pytest.approx(1.0, abs=1e-9)


class Thing:
    def __init__(self) -> None:
        self.x = 0.0
        self.pos = (0.0, 0.0)


def test_tween_reaches_target_exactly() -> None:
    thing = Thing()
    t = Tween(thing, "x", 10.0, 0.5, tween.linear)
    t.update(0.25)
    assert thing.x == pytest.approx(5.0)
    t.update(0.3)
    assert thing.x == 10.0
    assert t.done


def test_tween_tuples_and_delay_and_callback() -> None:
    thing = Thing()
    called = []
    t = Tween(
        thing, "pos", (4.0, 8.0), 1.0, tween.linear, delay=0.5, on_done=lambda: called.append(1)
    )
    t.update(0.4)
    assert thing.pos == (0.0, 0.0)
    t.update(0.2)  # 0.1 past the delay
    assert thing.pos == pytest.approx((0.4, 0.8))
    t.update(2.0)
    assert thing.pos == (4.0, 8.0)
    assert called == [1]


def test_animator_replaces_tween_on_same_attribute() -> None:
    thing = Thing()
    anim = Animator()
    first = anim.to(thing, "x", 100.0, 1.0)
    anim.update(0.5)
    second = anim.to(thing, "x", -5.0, 0.1)
    assert first.done
    anim.update(0.2)
    assert thing.x == -5.0
    assert second.done
    assert not anim.busy


def test_director_runs_sequence_with_waits() -> None:
    log: list[str] = []

    def script():
        log.append("a")
        yield 0.5
        log.append("b")
        yield None
        log.append("c")

    director = Director()
    director.run(script())
    assert log == ["a"], "runs up to the first wait immediately"
    director.update(0.3)
    assert log == ["a"]
    director.update(0.3)
    assert log == ["a", "b"]
    assert director.busy
    director.update(0.0)
    assert log == ["a", "b", "c"]
    assert not director.busy


def test_director_carries_leftover_time_through_consecutive_waits() -> None:
    log: list[str] = []

    def script():
        yield 0.1
        log.append("one")
        yield 0.1
        log.append("two")

    director = Director()
    director.run(script())
    director.update(0.25)
    assert log == ["one", "two"]


def test_director_waits_for_tweens_and_groups() -> None:
    thing = Thing()
    anim = Animator()
    log: list[str] = []

    def script():
        a = anim.to(thing, "x", 1.0, 0.2)
        b = anim.to(thing, "pos", (1.0, 1.0), 0.4)
        yield [a, b]
        log.append("both done")

    director = Director()
    director.run(script())
    for _ in range(3):
        anim.update(0.1)
        director.update(0.1)
    assert log == []
    anim.update(0.1)
    director.update(0.1)
    assert log == ["both done"]


def test_director_can_wait_on_another_script_and_cancel() -> None:
    director = Director()

    def child():
        yield 1.0

    def parent(handle):
        yield handle
        raise AssertionError("cancelled scripts must not resume")

    handle = director.run(child())
    director.run(parent(handle))
    director.update(0.5)
    director.cancel_all()
    director.update(5.0)
    assert not director.busy


def test_director_rejects_bad_yields() -> None:
    def script():
        yield "soon"

    with pytest.raises(TypeError):
        Director().run(script())
