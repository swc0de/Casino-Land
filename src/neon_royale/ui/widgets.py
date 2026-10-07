"""Interactive widgets with neon styling and sound feedback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import pygame

from ..core.chips import BETTING_CHIPS
from ..core.money import Cents, fmt
from . import fonts, theme
from .fx.glow import neon_frame, neon_text
from .fx.tween import ease_out_back, ease_out_cubic
from .render.chips import chip_top
from .theme import Color, lerp_color, scale_color

if TYPE_CHECKING:
    from ..audio.mixer import SoundBank


def _approach(value: float, target: float, rate: float, dt: float) -> float:
    """Exponential smoothing towards ``target`` (frame-rate independent)."""
    k = 1.0 - pow(0.5, dt * rate)
    return value + (target - value) * k


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: tuple[int, int, int, int] = (14, 8, 34, 210),
    border: Color | None = theme.PURPLE,
    radius: int = 14,
    width: int = 2,
) -> None:
    """A translucent rounded panel."""
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    if border is not None:
        pygame.draw.rect(panel, (*border, 200), panel.get_rect(), width, border_radius=radius)
    surface.blit(panel, rect)


class Button:
    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        label: str,
        on_click: Callable[[], None],
        *,
        color: Color = theme.PINK,
        font_size: int = 22,
        hotkey: int | None = None,
        sounds: SoundBank | None = None,
        enabled: bool = True,
        tooltip: str | None = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.color = color
        self.font_size = font_size
        self.hotkey = hotkey
        self.sounds = sounds
        self.enabled = enabled
        self.visible = True
        self.tooltip = tooltip
        self.hovered = False
        self.pressed = False
        self.hover_t = 0.0
        self.flash = 0.0

    def _activate(self) -> None:
        self.flash = 1.0
        if self.sounds:
            self.sounds.play("ui_click")
        self.on_click()

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if the event was used by this button."""
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            inside = self.rect.collidepoint(event.pos)
            if inside and not self.hovered and self.enabled and self.sounds:
                self.sounds.play("ui_hover", 0.6)
            self.hovered = inside
            return False
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.pressed
            self.pressed = False
            if was_pressed and self.rect.collidepoint(event.pos):
                self._activate()
                return True
        elif event.type == pygame.KEYDOWN and self.hotkey is not None and event.key == self.hotkey:
            self._activate()
            return True
        return False

    def update(self, dt: float) -> None:
        target = 1.0 if self.hovered and self.enabled else 0.0
        self.hover_t = _approach(self.hover_t, target, 14, dt)
        self.flash = max(0.0, self.flash - dt * 3)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        rect = self.rect.move(0, 2) if self.pressed else self.rect
        base = self.color if self.enabled else theme.TEXT_MUTED
        fill_color = lerp_color((16, 9, 38), scale_color(base, 0.35), 0.3 + 0.4 * self.hover_t)
        draw_panel(surface, rect, (*fill_color, 235), None, radius=12)
        frame = neon_frame(rect.size, base, width=3, corner=12, radius=8)
        intensity = (0.55 + 0.45 * self.hover_t + 0.3 * self.flash) if self.enabled else 0.0
        frame.draw(
            surface, rect.center, min(1.0, intensity), halo_strength=0.5 + 0.5 * self.hover_t
        )
        text_color = lerp_color(base, theme.WHITE, 0.25 + 0.6 * self.hover_t)
        if not self.enabled:
            text_color = theme.TEXT_MUTED
        text = fonts.get("display", self.font_size).render(self.label, True, text_color)
        surface.blit(text, text.get_rect(center=(rect.centerx, rect.centery + 1)))


class ChipRack:
    """The row of chips the player picks a bet size from."""

    def __init__(
        self,
        center: tuple[int, int],
        sounds: SoundBank | None = None,
        denominations: Sequence[Cents] = BETTING_CHIPS,
        diameter: int = 58,
        gap: int = 12,
    ) -> None:
        self.denominations = list(denominations)
        self.diameter = diameter
        self.sounds = sounds
        width = len(self.denominations) * diameter + (len(self.denominations) - 1) * gap
        left = center[0] - width // 2
        self.rects = [
            pygame.Rect(left + i * (diameter + gap), center[1] - diameter // 2, diameter, diameter)
            for i in range(len(self.denominations))
        ]
        self.selected = 1 if len(self.denominations) > 1 else 0
        self.affordable = [True] * len(self.denominations)
        self.lift = [0.0] * len(self.denominations)
        self.hover: int | None = None

    @property
    def value(self) -> Cents:
        return self.denominations[self.selected]

    def set_balance(self, balance: Cents) -> None:
        self.affordable = [d <= balance for d in self.denominations]
        if not self.affordable[self.selected]:
            options = [i for i, ok in enumerate(self.affordable) if ok]
            if options:
                self.selected = options[-1]

    def select(self, index: int) -> None:
        if 0 <= index < len(self.denominations) and self.affordable[index]:
            if index != self.selected and self.sounds:
                self.sounds.play("chip_clack", 0.7)
            self.selected = index

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hover = next(
                (i for i, r in enumerate(self.rects) if r.collidepoint(event.pos)), None
            )
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.select(i)
                    return True
        elif event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_9:
            self.select(event.key - pygame.K_1)
            return True
        return False

    def update(self, dt: float) -> None:
        for i in range(len(self.lift)):
            target = 1.0 if i == self.selected else (0.35 if i == self.hover else 0.0)
            self.lift[i] = _approach(self.lift[i], target, 16, dt)

    def draw(self, surface: pygame.Surface, time: float = 0.0) -> None:
        for i, (denom, rect) in enumerate(zip(self.denominations, self.rects, strict=True)):
            lift = self.lift[i]
            center = (rect.centerx, rect.centery - round(10 * lift))
            if i == self.selected:
                ring = neon_frame((self.diameter + 14, self.diameter + 14), theme.GOLD, 3, 999, 8)
                ring.draw(surface, center, 0.85 + 0.15 * abs(((time * 2) % 2) - 1))
            chip = chip_top(denom, self.diameter)
            if not self.affordable[i]:
                chip = chip.copy()
                chip.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(chip, chip.get_rect(center=center))


class CountingLabel:
    """A money readout that rolls to new values and flashes green or red."""

    def __init__(
        self,
        pos: tuple[int, int],
        value: Cents,
        caption: str = "",
        anchor: str = "midleft",
        size: int = 30,
        color: Color = theme.GOLD,
    ) -> None:
        self.pos = pos
        self.caption = caption
        self.anchor = anchor
        self.size = size
        self.color = color
        self.shown = float(value)
        self.start = float(value)
        self.target = value
        self.t = 1.0
        self.flash_color: Color = color
        self.flash = 0.0

    def set(self, value: Cents, animate: bool = True) -> None:
        if value == self.target:
            return
        self.flash_color = theme.WIN if value > self.target else theme.LOSE
        self.flash = 1.0 if animate else 0.0
        self.start = self.shown
        self.target = value
        self.t = 0.0 if animate else 1.0
        if not animate:
            self.shown = float(value)

    def update(self, dt: float) -> None:
        if self.t < 1.0:
            self.t = min(1.0, self.t + dt / 0.7)
            self.shown = self.start + (self.target - self.start) * ease_out_cubic(self.t)
        self.flash = max(0.0, self.flash - dt * 1.4)

    def draw(self, surface: pygame.Surface) -> pygame.Rect:
        color = lerp_color(self.color, self.flash_color, self.flash)
        value = round(self.shown)
        if self.target % 100 == 0:
            value = round(value / 100) * 100  # don't flash stray cents while rolling
        text = fonts.get("display", self.size).render(fmt(value), True, color)
        rect = text.get_rect(**{self.anchor: self.pos})
        if self.caption:
            cap = fonts.get("body_bold", max(14, self.size // 2)).render(
                self.caption.upper(), True, theme.TEXT_DIM
            )
            cap_rect = cap.get_rect(bottomleft=(rect.left, rect.top + 4))
            surface.blit(cap, cap_rect)
        surface.blit(text, rect)
        return rect


class Banner:
    """A big neon message that pops in, holds, and fades: "BLACKJACK!", "YOU WIN $350"."""

    def __init__(self) -> None:
        self.text = ""
        self.sub = ""
        self.color: Color = theme.GOLD
        self.age = 0.0
        self.hold = 0.0
        self.active = False
        self.center = (theme.WIDTH // 2, theme.HEIGHT // 2)

    def show(
        self,
        text: str,
        sub: str = "",
        color: Color = theme.GOLD,
        hold: float = 1.6,
        center: tuple[int, int] | None = None,
    ) -> None:
        self.text, self.sub, self.color, self.hold = text, sub, color, hold
        self.age = 0.0
        self.active = True
        self.center = center or (theme.WIDTH // 2, theme.HEIGHT // 2)

    def hide(self) -> None:
        self.active = False

    def update(self, dt: float) -> None:
        if self.active:
            self.age += dt
            if self.age > self.hold + 0.5:
                self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        pop = ease_out_back(min(1.0, self.age / 0.35))
        fade = 1.0 if self.age < self.hold else max(0.0, 1 - (self.age - self.hold) / 0.5)
        graphic = neon_text(self.text, "display", 64, self.color, 16)
        if pop < 0.999:
            scale = max(0.05, pop)
            for layer in (graphic.halo, graphic.core):
                scaled = pygame.transform.smoothscale_by(layer, scale)
                scaled.set_alpha(round(255 * fade))
                surface.blit(scaled, scaled.get_rect(center=self.center))
        else:
            graphic.draw(surface, self.center, fade)
        if self.sub:
            sub = fonts.get("display", 30).render(self.sub, True, theme.WHITE)
            sub.set_alpha(round(255 * fade * min(1.0, self.age / 0.4)))
            surface.blit(sub, sub.get_rect(center=(self.center[0], self.center[1] + 58)))


class Toast:
    """A small transient message near the top of the screen."""

    def __init__(self, y: int = 96) -> None:
        self.y = y
        self.items: list[list] = []  # [text, color, age]

    def show(self, text: str, color: Color = theme.TEXT) -> None:
        self.items = [i for i in self.items if i[0] != text][-2:]
        self.items.append([text, color, 0.0])

    def update(self, dt: float) -> None:
        for item in self.items:
            item[2] += dt
        self.items = [i for i in self.items if i[2] < 2.6]

    def draw(self, surface: pygame.Surface) -> None:
        for n, (text, color, age) in enumerate(reversed(self.items)):
            alpha = min(1.0, age / 0.15, (2.6 - age) / 0.4)
            label = fonts.get("body_bold", 24).render(text, True, color)
            box = label.get_rect(center=(theme.WIDTH // 2, self.y + n * 44)).inflate(32, 12)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (10, 6, 24, 220), panel.get_rect(), border_radius=10)
            pygame.draw.rect(panel, (*color, 180), panel.get_rect(), 2, border_radius=10)
            panel.blit(label, label.get_rect(center=panel.get_rect().center))
            panel.set_alpha(round(255 * max(0.0, alpha)))
            surface.blit(panel, box)


class Slider:
    """A horizontal 0..1 slider (volumes, bet sizing)."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        value: float,
        on_change: Callable[[float], None],
        color: Color = theme.CYAN,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.value = max(0.0, min(1.0, value))
        self.on_change = on_change
        self.color = color
        self.dragging = False

    def _set_from(self, x: int) -> None:
        value = max(0.0, min(1.0, (x - self.rect.left) / max(1, self.rect.width)))
        if value != self.value:
            self.value = value
            self.on_change(value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(16, 24).collidepoint(event.pos):
                self.dragging = True
                self._set_from(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from(event.pos[0])
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        track = self.rect.inflate(0, -self.rect.height + 6)
        pygame.draw.rect(surface, (40, 30, 70), track, border_radius=3)
        filled = track.copy()
        filled.width = round(track.width * self.value)
        pygame.draw.rect(surface, self.color, filled, border_radius=3)
        knob = (track.left + filled.width, track.centery)
        pygame.draw.circle(surface, theme.WHITE, knob, 10)
        pygame.draw.circle(surface, self.color, knob, 10, 3)
