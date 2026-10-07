"""Headless checks for the procedural art, effects and widgets."""

from __future__ import annotations

import random
from collections.abc import Iterator

import pygame
import pytest

from neon_royale.core.cards import Card, Rank, Suit, full_deck
from neon_royale.core.chips import DENOMINATIONS
from neon_royale.core.money import dollars
from neon_royale.ui import caches
from neon_royale.ui.fx.glow import neon_frame, neon_text
from neon_royale.ui.fx.marquee import LEVELS, Marquee, bulb_sprites, perimeter_points
from neon_royale.ui.fx.neon import Flicker, NeonSign
from neon_royale.ui.fx.particles import ParticleSystem
from neon_royale.ui.fx.signboard import SignBoard
from neon_royale.ui.render import backdrop, cards, chips
from neon_royale.ui.widgets import Button, ChipRack, CountingLabel, Slider


@pytest.fixture(autouse=True)
def display() -> Iterator[pygame.Surface]:
    pygame.init()
    caches.clear_all()
    screen = pygame.display.set_mode((1280, 720))
    yield screen
    caches.clear_all()
    pygame.quit()


def test_every_card_face_renders_at_the_requested_size() -> None:
    for card in full_deck():
        face = cards.card_face(card, 80)
        assert face.get_size() == cards.card_size(80) == (80, 112)
    assert cards.card_back(80).get_size() == (80, 112)
    assert cards.card_shadow(80).get_width() > 80


def test_red_and_black_suits_use_different_ink() -> None:
    red = cards.card_face(Card(Rank.ACE, Suit.HEARTS), 120)
    black = cards.card_face(Card(Rank.ACE, Suit.SPADES), 120)
    center = (60, 84)
    r, g, b, _ = red.get_at(center)
    assert r > 150 and g < 80
    r, g, b, _ = black.get_at(center)
    assert max(r, g, b) < 80


def test_chip_art_for_every_denomination() -> None:
    for denom in DENOMINATIONS:
        assert chips.chip_top(denom, 48).get_size() == (48, 48)
        assert chips.chip_piece(denom, 48).get_width() == 48


def test_stacks_split_into_columns() -> None:
    columns = chips.stack_columns(dollars(1_111), per_column=3)
    assert [len(c) for c in columns] == [3, 2]  # 1000, 100, 5, 5, 1
    assert chips.stack_columns(0) == []
    surface = pygame.Surface((400, 400), pygame.SRCALPHA)
    area = chips.draw_amount(surface, dollars(2_780), (200, 300), 40)
    assert area.width > 0 and area.bottom <= 300


def test_neon_graphics_are_padded_for_their_halo() -> None:
    graphic = neon_text("HELLO", "display", 32, (255, 0, 128), 10)
    w, h = graphic.content_size
    assert graphic.size == (w + 40, h + 40)
    frame = neon_frame((200, 100), (0, 255, 255))
    surface = pygame.Surface((400, 300))
    rect = frame.draw(surface, (200, 150), 0.5)
    assert rect.center == (200, 150)


def test_perimeter_points_are_on_the_rectangle() -> None:
    rect = pygame.Rect(10, 20, 300, 100)
    points = perimeter_points(rect, 25)
    assert len(points) == round(2 * (300 + 100) / 25)
    for x, y in points:
        on_edge = x in (rect.left, rect.right) or y in (rect.top, rect.bottom)
        assert on_edge


def test_marquee_patterns_stay_in_range() -> None:
    marquee = Marquee(pygame.Rect(0, 0, 400, 200), rng=random.Random(1))
    surface = pygame.Surface((420, 220))
    for pattern in ("chase", "alternate", "wave", "sparkle", "steady"):
        marquee.pattern = pattern
        for _ in range(10):
            marquee.update(0.05)
            assert all(0.0 <= marquee.brightness(i) <= 1.0 for i in range(len(marquee.points)))
        marquee.draw(surface)
    marquee.celebrate(1.0)
    marquee.update(0.1)
    marquee.draw(surface, offset=(0, -4))
    assert len(bulb_sprites((255, 255, 255), 5)) == LEVELS


def test_flicker_power_on_ends_lit_and_reports_strikes() -> None:
    strikes = []
    flicker = Flicker(random.Random(4), stutter_rate=0.0, on_stutter=lambda: strikes.append(1))
    flicker.power_on(delay=0.2)
    assert flicker.value == 0.0 or flicker.level == 0.0
    for _ in range(120):
        flicker.update(1 / 60)
    assert flicker.level == 1.0
    assert flicker.value > 0.9
    assert strikes, "striking a tube should trigger the buzz callback"
    flicker.power_off()
    assert flicker.value == 0.0


def test_sign_board_intro_and_skip() -> None:
    board = SignBoard(pygame.Rect(0, 0, 800, 240), "NEON", random.Random(2), subtitle="CASINO")
    board.power_on(delay=0.5, duration=1.0)
    assert not board.lit
    board.skip_intro()
    assert board.lit
    board.update(0.1)
    board.draw(pygame.Surface((800, 240)))


def test_neon_sign_measures_its_letters() -> None:
    sign = NeonSign("AB C", "display", 40, (255, 0, 0), random.Random(0))
    assert len(sign.letters) == 3, "spaces take room but have no tube"
    assert sign.width > 0


def test_particles_expire() -> None:
    system = ParticleSystem(random.Random(0), limit=50)
    system.burst((100, 100), count=30, life=(0.2, 0.3))
    system.confetti(pygame.Rect(0, 0, 200, 200), count=40)
    assert len(system) == 50, "limit caps the pool"
    surface = pygame.Surface((300, 300))
    system.draw(surface)
    for _ in range(300):
        system.update(1 / 60)
    assert len(system) == 0


def test_backdrops_render() -> None:
    assert backdrop.felt((320, 180)).get_size() == (320, 180)
    assert backdrop.casino_night(400).get_size() == (1280, 720)
    assert backdrop.wood_rail((100, 20)).get_size() == (100, 20)


def _click(widget, pos: tuple[int, int]) -> None:
    widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


def test_button_click_hotkey_and_disabled() -> None:
    clicks = []
    button = Button((10, 10, 100, 40), "GO", lambda: clicks.append(1), hotkey=pygame.K_g)
    _click(button, (50, 30))
    button.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g))
    _click(button, (500, 300))
    assert clicks == [1, 1]
    button.enabled = False
    _click(button, (50, 30))
    assert clicks == [1, 1]
    button.update(0.1)
    button.draw(pygame.Surface((200, 100)))


def test_button_needs_press_and_release_inside() -> None:
    clicks = []
    button = Button((10, 10, 100, 40), "GO", lambda: clicks.append(1))
    button.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 30), button=1))
    button.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(300, 300), button=1))
    assert clicks == []


def test_chip_rack_selection_respects_balance() -> None:
    rack = ChipRack((300, 100))
    _click(rack, rack.rects[3].center)
    assert rack.value == dollars(100)
    rack.set_balance(dollars(30))
    assert rack.value == dollars(25), "falls back to the largest affordable chip"
    rack.select(5)
    assert rack.value == dollars(25)
    rack.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
    assert rack.value == dollars(1)
    rack.update(0.1)
    rack.draw(pygame.Surface((600, 200)), 1.0)


def test_counting_label_rolls_to_target() -> None:
    label = CountingLabel((0, 0), 1000)
    label.set(5000)
    label.update(0.1)
    assert 1000 < label.shown < 5000
    for _ in range(20):
        label.update(0.1)
    assert round(label.shown) == 5000
    assert label.flash_color != label.color
    label.draw(pygame.Surface((300, 80)))


def test_slider_drag() -> None:
    values = []
    slider = Slider((0, 0, 200, 20), 0.5, values.append)
    slider.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 10), button=1))
    slider.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 10), rel=(0, 0), buttons=(1, 0, 0))
    )
    slider.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(400, 10), button=1))
    assert values == [0.25, 1.0]
    slider.draw(pygame.Surface((220, 40)))
