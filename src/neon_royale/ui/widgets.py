"""Interactive widgets in brass, lacquer and gold leaf, with sound feedback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import pygame

from ..core.chips import BETTING_CHIPS
from ..core.money import Cents, fmt
from . import fonts, theme
from .caches import surface_cache
from .fx.tween import ease_out_back, ease_out_cubic
from .render.chips import chip_top
from .render.decor import _panel_fill, draw_gilded_frame, engraved_text, metallic
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
    fill: tuple[int, int, int, int] = (22, 12, 8, 230),
    border: Color | None = theme.GOLD,
    radius: int = 14,
    width: int = 2,
) -> None:
    """A lacquered panel; ``border`` adds a gold moulding of ``width`` px."""
    if rect.width <= 0 or rect.height <= 0:
        return
    panel = _panel_fill(rect.size, fill[:3], radius)
    panel.set_alpha(fill[3] if len(fill) > 3 else 255)
    surface.blit(panel, rect)
    if border is not None:
        draw_gilded_frame(surface, rect, max(1, width), radius)


BUTTON_KINDS = {
    # face gradient top -> bottom, text colour, rim
    "primary": (((255, 236, 170), (222, 178, 80), (160, 112, 36)), (48, 28, 6)),
    "secondary": (((58, 36, 26), (26, 14, 10), (14, 8, 6)), theme.GOLD_LIGHT),
    "danger": (((150, 30, 40), (100, 14, 24), (60, 6, 14)), theme.GOLD_LIGHT),
}


@surface_cache(maxsize=128)
def _button_face(size: tuple[int, int], kind: str, state: str) -> pygame.Surface:
    """Pre-rendered button body for ``state`` in normal, hover, pressed, disabled."""
    ramp, _ = BUTTON_KINDS[kind]
    if state == "hover":
        ramp = tuple(lerp_color(c, (255, 255, 255), 0.18) for c in ramp)
    elif state == "pressed":
        ramp = tuple(scale_color(c, 0.82) for c in ramp)
    elif state == "disabled":
        ramp = tuple(lerp_color(scale_color(c, 0.55), (40, 34, 30), 0.6) for c in ramp)
    w, h = size
    radius = min(12, h // 2)
    surf = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 120), shadow.get_rect(), border_radius=radius)
    surf.blit(shadow, (5, 6))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255), mask.get_rect(), border_radius=radius)
    face = metallic(mask, (ramp[0], ramp[1], ramp[2], ramp[1]))
    surf.blit(face, (4, 4))
    gloss = pygame.Surface((w - 8, max(2, h // 2 - 4)), pygame.SRCALPHA)
    pygame.draw.rect(gloss, (255, 255, 255, 36), gloss.get_rect(), border_radius=radius)
    surf.blit(gloss, (8, 7))
    rim = theme.GOLD if state != "disabled" else (110, 92, 70)
    pygame.draw.rect(surf, (40, 24, 8), pygame.Rect(4, 4, w, h), 3, border_radius=radius)
    pygame.draw.rect(surf, rim, pygame.Rect(5, 5, w - 2, h - 2), 2, border_radius=radius)
    return surf


class Button:
    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        label: str,
        on_click: Callable[[], None],
        *,
        kind: str = "secondary",
        font_size: int = 22,
        hotkey: int | None = None,
        sounds: SoundBank | None = None,
        enabled: bool = True,
        tooltip: str | None = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.kind = kind
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
        size = rect.size
        if not self.enabled:
            surface.blit(_button_face(size, self.kind, "disabled"), rect.move(-4, -4))
        else:
            state = "pressed" if self.pressed else "normal"
            surface.blit(_button_face(size, self.kind, state), rect.move(-4, -4))
            if self.hover_t > 0.02 and not self.pressed:
                hover = _button_face(size, self.kind, "hover")
                hover.set_alpha(round(255 * self.hover_t))
                surface.blit(hover, rect.move(-4, -4))
                hover.set_alpha(255)
            if self.flash > 0:
                draw_gilded_frame(surface, rect.inflate(6, 6), 2, 14, glow=self.flash)
        _, text_color = BUTTON_KINDS[self.kind]
        if not self.enabled:
            text_color = (130, 116, 96)
        font = fonts.get("display", self.font_size)
        if self.kind != "primary" and self.enabled:
            shade = font.render(self.label, True, (0, 0, 0))
            surface.blit(shade, shade.get_rect(center=(rect.centerx + 1, rect.centery + 2)))
        text = font.render(self.label, True, text_color)
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
                ring = pygame.Rect(0, 0, self.diameter + 12, self.diameter + 12)
                ring.center = center
                pulse = 0.55 + 0.45 * abs(((time * 1.5) % 2) - 1)
                draw_gilded_frame(surface, ring, 3, ring.width // 2, glow=round(pulse, 1))
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
        font = fonts.get("numbers", self.size)
        text = font.render(fmt(value), True, color)
        rect = text.get_rect(**{self.anchor: self.pos})
        shade = font.render(fmt(value), True, (0, 0, 0))
        surface.blit(shade, rect.move(1, 2))
        if self.caption:
            cap = fonts.get("body_bold", max(13, self.size * 4 // 9)).render(
                " ".join(self.caption.upper()), True, theme.TEXT_DIM
            )
            cap_rect = cap.get_rect(bottomleft=(rect.left, rect.top + 4))
            surface.blit(cap, cap_rect)
        surface.blit(text, rect)
        return rect


class Banner:
    """A big gold-leaf message that pops in, holds and fades: "BLACKJACK!", "YOU WIN $350"."""

    def __init__(self) -> None:
        self.text = ""
        self.sub = ""
        self.color: Color = theme.GOLD
        self.age = 0.0
        self.hold = 0.0
        self.active = False
        self.center = (theme.WIDTH // 2, theme.HEIGHT // 2)
        self.size = 64

    def show(
        self,
        text: str,
        sub: str = "",
        color: Color = theme.GOLD,
        hold: float = 1.6,
        center: tuple[int, int] | None = None,
        size: int = 64,
    ) -> None:
        self.text, self.sub, self.color, self.hold = text, sub, color, hold
        self.size = size
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
        style = _banner_style(self.color)
        graphic = engraved_text(self.text, "display_black", self.size, style, glow=0.7)
        if pop < 0.999:
            scaled = pygame.transform.smoothscale_by(graphic.surface, max(0.05, pop))
            scaled.set_alpha(round(255 * fade))
            surface.blit(scaled, scaled.get_rect(center=self.center))
        else:
            graphic.draw(surface, self.center, fade)
        if self.sub:
            sub = engraved_text(self.sub, "display", max(18, self.size * 30 // 64), "cream")
            offset = self.size * 62 // 64
            sub.draw(
                surface,
                (self.center[0], self.center[1] + offset),
                fade * min(1.0, self.age / 0.4),
            )


def _banner_style(color: Color) -> str:
    if color == theme.WIN:
        return "emerald"
    if color == theme.LOSE:
        return "ruby"
    if color in (theme.TEXT, theme.WARM_WHITE, theme.TEXT_DIM):
        return "cream"
    return "gold"


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
            alpha = max(0.0, min(1.0, age / 0.15, (2.6 - age) / 0.4))
            label = fonts.get("body_bold", 21).render(text, True, color)
            box = label.get_rect(center=(theme.WIDTH // 2, self.y + n * 46)).inflate(44, 16)
            layer = pygame.Surface((box.width + 8, box.height + 8), pygame.SRCALPHA)
            inner = pygame.Rect(4, 4, box.width, box.height)
            draw_panel(layer, inner, (20, 11, 7, 235), theme.GOLD, 10, 2)
            pygame.draw.circle(layer, theme.GOLD, (inner.left + 12, inner.centery), 3)
            pygame.draw.circle(layer, theme.GOLD, (inner.right - 12, inner.centery), 3)
            layer.blit(label, label.get_rect(center=inner.center))
            layer.set_alpha(round(255 * alpha))
            surface.blit(layer, box.move(-4, -4))


class Slider:
    """A horizontal 0..1 slider (volumes, bet sizing)."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        value: float,
        on_change: Callable[[float], None],
        color: Color = theme.GOLD,
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
        track = self.rect.inflate(0, -self.rect.height + 8)
        pygame.draw.rect(surface, (8, 4, 2), track.move(0, 1), border_radius=4)
        pygame.draw.rect(surface, (40, 26, 18), track, border_radius=4)
        filled = track.copy()
        filled.width = round(track.width * self.value)
        if filled.width > 0:
            pygame.draw.rect(surface, scale_color(self.color, 0.8), filled, border_radius=4)
            pygame.draw.line(surface, theme.GOLD_LIGHT, (filled.left + 3, filled.top + 1),
                             (filled.right - 3, filled.top + 1))  # fmt: skip
        knob = (track.left + filled.width, track.centery)
        pygame.draw.circle(surface, (0, 0, 0), (knob[0] + 1, knob[1] + 2), 11)
        pygame.draw.circle(surface, theme.GOLD_DARK, knob, 11)
        pygame.draw.circle(surface, theme.GOLD, knob, 9)
        pygame.draw.circle(surface, theme.GOLD_LIGHT, (knob[0] - 3, knob[1] - 3), 3)
