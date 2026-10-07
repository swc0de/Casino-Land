"""Pop-up panels drawn over the current screen: settings, stats and help."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import pygame

from ...core.money import fmt
from .. import fonts, theme
from ..render.decor import crown, engraved_text, ornament_rule
from ..stage import Stage
from ..widgets import Slider, draw_panel

if TYPE_CHECKING:
    from ..app import App


class Overlay(Stage):
    overlay = True
    ambience = None  # leave the room's ambience as it is

    def __init__(self, app: App, title: str, size: tuple[int, int], color=theme.GOLD) -> None:
        super().__init__(app)
        self.title = title
        self.color = color
        self.panel = pygame.Rect(0, 0, *size)
        self.panel.center = (theme.WIDTH // 2, theme.HEIGHT // 2)
        self.shade = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 160))
        self.age = 0.0

    def close(self) -> None:
        self.sound.play("ui_click", 0.7)
        self.app.save()
        self.app.scenes.pop()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_F1):
            self.close()
            return True
        return super().handle_event(event)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.shade, (0, 0))
        draw_panel(surface, self.panel, (26, 14, 9, 250), theme.GOLD, 20, 4)
        inner = self.panel.inflate(-18, -18)
        pygame.draw.rect(surface, theme.GOLD_DARK, inner, 1, border_radius=14)
        title = engraved_text(self.title, "display", 32, "gold", glow=0.3)
        title.draw(surface, (self.panel.centerx, self.panel.top + 46))
        ornament_rule(surface, (self.panel.centerx, self.panel.top + 76), 300)
        crown(surface, (self.panel.centerx, self.panel.top - 2), 44)

    def draw_top(self, surface: pygame.Surface) -> None:
        self.draw_buttons(surface)
        self.draw_overlays(surface)


class SettingsScene(Overlay):
    def __init__(self, app: App) -> None:
        super().__init__(app, "SETTINGS", (640, 520))
        settings = app.settings
        left = self.panel.left + 300
        top = self.panel.top + 110
        self.sliders: list[tuple[str, Slider]] = []
        for i, (label, attr) in enumerate(
            (("Master volume", "master_volume"), ("Effects", "sfx_volume"),
             ("Casino ambience", "ambience_volume"))
        ):  # fmt: skip
            slider = Slider(
                (left, top + i * 52, 260, 24), getattr(settings, attr), self._setter(attr)
            )
            self.sliders.append((label, slider))
        self.toggles: list[tuple[str, str, object]] = []
        for i, (label, attr) in enumerate(
            (("Fullscreen (F11)", "fullscreen"), ("Fast animations", "fast_animations"),
             ("Frame-rate overlay (F3)", "show_fps"))
        ):  # fmt: skip
            y = top + 156 + i * 52
            button = self.button(
                (left + 150, y - 4, 110, 40),
                "",
                lambda a=attr: self._toggle(a),
                font_size=18,
            )
            self.toggles.append((label, attr, button))
        self.confirm_reset = False
        self.reset_button = self.button(
            (self.panel.left + 40, self.panel.bottom - 76, 260, 50),
            "RESET BANKROLL",
            self._reset,
            kind="danger",
            font_size=18,
        )
        self.button(
            (self.panel.right - 200, self.panel.bottom - 76, 160, 50),
            "DONE",
            self.close,
            kind="primary",
            hotkey=pygame.K_RETURN,
        )

    def _setter(self, attr: str) -> Callable[[float], None]:
        def set_value(value: float) -> None:
            setattr(self.app.settings, attr, round(value, 2))
            self.sound.apply_volumes()
            self.sound.play("chip_clack", 0.6)

        return set_value

    def _toggle(self, attr: str) -> None:
        settings = self.app.settings
        if attr == "fullscreen":
            self.app._set_fullscreen(not settings.fullscreen)
        else:
            setattr(settings, attr, not getattr(settings, attr))

    def _reset(self) -> None:
        if not self.confirm_reset:
            self.confirm_reset = True
            self.reset_button.label = "CLICK TO CONFIRM"
            return
        self.app.casino.reset()
        self.app.save()
        self.confirm_reset = False
        self.reset_button.label = "RESET BANKROLL"
        self.toast.show(f"Fresh start: {fmt(self.app.casino.balance)} in chips", theme.GOLD_LIGHT)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if super().handle_event(event):
            return True
        return any(slider.handle_event(event) for _, slider in self.sliders)

    def update(self, dt: float) -> None:
        super().update(dt)
        for _, attr, button in self.toggles:
            on = bool(getattr(self.app.settings, attr))
            button.label = "ON" if on else "OFF"
            button.kind = "primary" if on else "secondary"

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        font = fonts.get("body_bold", 22)
        x = self.panel.left + 44
        for label, slider in self.sliders:
            text = font.render(label, True, theme.TEXT)
            surface.blit(text, text.get_rect(midleft=(x, slider.rect.centery)))
            slider.draw(surface)
            pct = fonts.get("body", 18).render(
                f"{round(slider.value * 100)}%", True, theme.TEXT_DIM
            )
            surface.blit(pct, pct.get_rect(midleft=(slider.rect.right + 18, slider.rect.centery)))
        for label, _, button in self.toggles:
            text = font.render(label, True, theme.TEXT)
            surface.blit(text, text.get_rect(midleft=(x, button.rect.centery)))
        self.draw_top(surface)


class StatsScene(Overlay):
    GAMES = (("roulette", "Roulette"), ("blackjack", "Blackjack"), ("poker", "Hold'em"))

    def __init__(self, app: App) -> None:
        super().__init__(app, "YOUR RECORD", (760, 440))
        self.button(
            (self.panel.centerx - 80, self.panel.bottom - 74, 160, 50),
            "DONE",
            self.close,
            kind="primary",
            hotkey=pygame.K_RETURN,
        )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        profile = self.app.casino.sync()
        columns = ("", "Rounds", "Wagered", "Won back", "Net", "Best win")
        xs = [self.panel.left + 40] + [self.panel.left + 210 + i * 108 for i in range(5)]
        y = self.panel.top + 104
        head = fonts.get("body_bold", 19)
        for x, name in zip(xs, columns, strict=True):
            text = head.render(name.upper(), True, theme.TEXT_DIM)
            surface.blit(text, (x, y))
        body = fonts.get("display", 19)
        total_net = 0
        for row, (key, title) in enumerate(self.GAMES):
            stats = profile.stats.get(key)
            if stats is None:
                continue
            total_net += stats.net
            cy = y + 46 + row * 46
            values = (
                title,
                str(stats.rounds),
                fmt(stats.wagered, compact=True),
                fmt(stats.returned, compact=True),
                fmt(stats.net, signed=True, compact=True),
                fmt(max(0, stats.biggest_win), compact=True),
            )
            for i, (x, value) in enumerate(zip(xs, values, strict=True)):
                color = theme.TEXT
                if i == 4:
                    color = (
                        theme.WIN if stats.net > 0 else theme.LOSE if stats.net < 0 else theme.TEXT
                    )
                text = body.render(value, True, color)
                surface.blit(text, (x, cy))
        summary = fonts.get("body_bold", 21).render(
            f"Bankroll {fmt(profile.balance)}   ·   Overall {fmt(total_net, signed=True)}"
            f"   ·   House comps {profile.comps_received}",
            True,
            theme.GOLD,
        )
        surface.blit(
            summary, summary.get_rect(center=(self.panel.centerx, self.panel.bottom - 112))
        )
        self.draw_top(surface)


def wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


class HelpScene(Overlay):
    def __init__(self, app: App, title: str, rules: Sequence[str], keys: Sequence[str]) -> None:
        super().__init__(app, title, (820, 540))
        self.rules = rules
        self.keys = keys
        self.button(
            (self.panel.centerx - 80, self.panel.bottom - 72, 160, 50),
            "GOT IT",
            self.close,
            kind="primary",
            hotkey=pygame.K_RETURN,
        )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        font = fonts.get("body_medium", 21)
        x = self.panel.left + 44
        y = self.panel.top + 92
        width = self.panel.width - 88
        for rule in self.rules:
            for i, line in enumerate(wrap(rule, font, width - 22)):
                if i == 0:
                    pygame.draw.polygon(
                        surface,
                        theme.GOLD,
                        [(x + 6, y + 7), (x + 11, y + 12), (x + 6, y + 17), (x + 1, y + 12)],
                    )
                text = font.render(line, True, theme.TEXT)
                surface.blit(text, (x + 22, y))
                y += 27
            y += 6
        y += 6
        head = fonts.get("display", 18).render("KEYS", True, theme.GOLD)
        surface.blit(head, (x, y))
        y += 30
        key_font = fonts.get("body_bold", 20)
        for line in self.keys:
            text = key_font.render(line, True, theme.TEXT_DIM)
            surface.blit(text, (x, y))
            y += 26
        self.draw_top(surface)


HELP = {
    "roulette": (
        "HOW TO PLAY ROULETTE",
        (
            "European single-zero wheel. Pick a chip, then click a number, a line between "
            "numbers, or a corner to bet on it. Right-click a bet to take it back.",
            "Straight 35:1 · Split 17:1 · Street and Trio 11:1 · Corner and First four 8:1 · "
            "Six line 5:1 · Dozen and Column 2:1 · Red/Black, Odd/Even, 1-18/19-36 pay 1:1.",
            "$1 minimum per bet and $5,000 total on the layout. Zero loses every outside bet.",
        ),
        (
            "1-6 choose a chip   ·   Space spin   ·   Backspace undo",
            "C clear   ·   D double   ·   R rebet   ·   Esc back to the lobby",
        ),
    ),
    "blackjack": (
        "HOW TO PLAY BLACKJACK",
        (
            "Beat the dealer by getting closer to 21 without going over. Face cards count "
            "10, aces 1 or 11. A two-card 21 is a blackjack and pays 3:2.",
            "The dealer stands on all 17s and checks for blackjack with an ace or ten showing. "
            "Insurance pays 2:1 when the dealer shows an ace.",
            "Double on any two cards (one more card, bet doubled). Split equal cards into up "
            "to four hands; split aces get one card each. Surrender your first two cards for "
            "half your bet back.",
        ),
        (
            "Click the circle to bet   ·   Space deal   ·   H hit   ·   S stand",
            "D double   ·   P split   ·   R surrender   ·   HINT shows the best play",
        ),
    ),
    "poker": (
        "HOW TO PLAY HOLD'EM",
        (
            "Make the best five-card hand from your two cards and the five shared cards. "
            "Bet, call, raise or fold over four rounds: before the flop, flop, turn, river.",
            "Hands from best to worst: royal flush, straight flush, four of a kind, full "
            "house, flush, straight, three of a kind, two pair, pair, high card.",
            "No-Limit: you can bet any amount up to your stack. Blinds are $5/$10 and the "
            "minimum raise is the size of the last bet or raise.",
        ),
        (
            "F fold   ·   C check or call   ·   R bet or raise   ·   Mouse wheel sizes a raise",
            "Space skips the pause between hands   ·   Esc cashes out to the lobby",
        ),
    ),
}


def open_help(app: App, game: str) -> None:
    title, rules, keys = HELP[game]
    app.sound.play("ui_click")
    app.scenes.push(HelpScene(app, title, rules, keys))
