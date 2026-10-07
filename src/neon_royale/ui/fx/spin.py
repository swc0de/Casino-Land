"""Roulette wheel and ball motion.

The winning number is decided by the rules engine *before* the animation starts.
The ball's path is then built backwards from that pocket: its angle relative to the
wheel eases from many turns away down to exactly the pocket's angle, so however the
wheel is turning, the ball always comes to rest in the right place.

Angles are radians clockwise from 12 o'clock. Ball height is a fraction where 1.0 is
the outer track and 0.0 the bottom of a pocket. Nothing here touches pygame.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

IDLE_SPEED = 0.35  # wheel turns slowly even between spins (rad/s)
SPIN_SPEED = 1.5
DROP_AT = 0.58  # fraction of the flight when the ball leaves the track
BOUNCE_FROM = 0.74  # fraction when it starts hopping between pockets


def _ease_out(u: float, power: float = 2.4) -> float:
    return 1 - (1 - u) ** power


@dataclass
class BallFlight:
    pocket_angle: float  # target angle relative to the wheel
    duration: float
    turns: float  # relative turns travelled before settling
    seed: int
    elapsed: float = 0.0

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def settled(self) -> bool:
        return self.elapsed >= self.duration

    def relative_angle(self) -> float:
        u = self.progress
        travel = self.turns * math.tau * (1 - _ease_out(u))
        wobble = 0.0
        if u > BOUNCE_FROM:
            k = (u - BOUNCE_FROM) / (1 - BOUNCE_FROM)
            wobble = 0.22 * math.sin(k * 23 + self.seed) * (1 - k) ** 2
        # The ball runs anticlockwise relative to the wheel, so it approaches from "ahead".
        return self.pocket_angle + travel + wobble

    def height(self) -> float:
        u = self.progress
        if u < DROP_AT:
            return 1.0
        if u < BOUNCE_FROM:
            k = (u - DROP_AT) / (BOUNCE_FROM - DROP_AT)
            return 1.0 - 0.65 * k * k
        k = (u - BOUNCE_FROM) / (1 - BOUNCE_FROM)
        return 0.35 * abs(math.sin(k * math.pi * 3.5)) * (1 - k) ** 1.6

    def relative_speed(self) -> float:
        """How fast the ball is moving, 0..1, for sound levels."""
        return (1 - self.progress) ** 1.4


class WheelSpin:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.wheel_angle = self.rng.uniform(0, math.tau)
        self.wheel_speed = IDLE_SPEED
        self.flight: BallFlight | None = None
        self.ball_relative = 0.0  # where a resting ball sits on the wheel
        self.has_ball = False
        self._last_bounce_phase = 0

    def launch(self, pocket_index: int, pocket_count: int, duration: float = 7.0) -> None:
        angle = pocket_index * math.tau / pocket_count
        self.flight = BallFlight(
            pocket_angle=angle,
            duration=duration,
            turns=self.rng.uniform(7.5, 9.5),
            seed=self.rng.randint(0, 1000),
        )
        self.wheel_speed = SPIN_SPEED
        self.has_ball = True
        self._last_bounce_phase = 0

    @property
    def spinning(self) -> bool:
        return self.flight is not None and not self.flight.settled

    def ball_angle(self) -> float:
        """World angle of the ball."""
        relative = self.flight.relative_angle() if self.flight else self.ball_relative
        return self.wheel_angle + relative

    def ball_height(self) -> float:
        return self.flight.height() if self.flight else 0.0

    def update(self, dt: float) -> list[str]:
        """Advance the motion; returns events: "drop", "tick", "settled"."""
        events: list[str] = []
        target = SPIN_SPEED if self.spinning else IDLE_SPEED
        # The croupier's push decays gradually back towards the idle turn.
        self.wheel_speed += (target - self.wheel_speed) * min(1.0, dt * 0.35)
        self.wheel_angle = (self.wheel_angle + self.wheel_speed * dt) % math.tau
        flight = self.flight
        if flight is None or flight.settled:
            return events
        before = flight.progress
        flight.elapsed += dt
        after = flight.progress
        if before < DROP_AT <= after:
            events.append("drop")
        if before < (DROP_AT + BOUNCE_FROM) / 2 <= after:
            events.append("tick")  # clips a deflector on the way down
        if after > BOUNCE_FROM:
            k = (after - BOUNCE_FROM) / (1 - BOUNCE_FROM)
            phase = int(k * 3.5)
            if phase > self._last_bounce_phase:
                self._last_bounce_phase = phase
                events.append("tick")
        if flight.settled:
            self.ball_relative = flight.pocket_angle
            self.flight = None
            events.append("settled")
        return events

    def clear_ball(self) -> None:
        self.flight = None
        self.has_ball = False
