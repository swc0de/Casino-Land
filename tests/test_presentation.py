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
from neon_royale.ui.fx.marquee import LEVELS, Marquee, bulb_sprites, perimeter_points
from neon_royale.ui.fx.particles import ParticleSystem
from neon_royale.ui.render import backdrop, cards, chips, decor
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


def test_engraved_lettering_is_padded_and_cached() -> None:
    text = decor.engraved_text("ROYALE", "logo", 40, "gold", glow=0.5)
    w, h = text.content_size
    assert text.size == (w + 2 * text.margin, h + 2 * text.margin)
    assert decor.engraved_text("ROYALE", "logo", 40, "gold", glow=0.5) is text
    surface = pygame.Surface((400, 200))
    assert text.draw(surface, (200, 100), 0.5).center == (200, 100)
    # The metallic face is gold: warm, much more red than blue, and opaque.
    block = pygame.Surface((20, 40), pygame.SRCALPHA)
    block.fill((255, 255, 255, 255))
    r, _, b, a = decor.metallic(block, decor.GOLD_RAMP).get_at((10, 20))
    assert r > b + 80 and a == 255
    for style in ("cream", "silver", "ruby", "emerald"):
        decor.engraved_text("A", "display", 20, style)


def test_furnishings_render() -> None:
    assert decor.carpet((300, 200)).get_size() == (300, 200)
    assert decor.velvet((300, 200)).get_size() == (300, 200)
    assert decor.wood((120, 30)).get_size() == (120, 30)
    assert decor.wood((30, 120), vertical=True).get_size() == (30, 120)
    assert (
        decor.light_pool((200, 100)).get_at((100, 50)).a
        > decor.light_pool((200, 100)).get_at((2, 2)).a
    )
    assert decor.brass_plaque((200, 40), "ROULETTE").get_size() == (200, 40)
    assert decor.table_background().get_size() == (1280, 720)
    surface = pygame.Surface((400, 300), pygame.SRCALPHA)
    decor.padded_ellipse(surface, pygame.Rect(20, 20, 300, 200), 20)
    decor.padded_band(surface, pygame.Rect(0, 250, 400, 20))
    decor.lacquer_panel(surface, pygame.Rect(10, 10, 120, 50), glow=0.5)
    decor.draw_gilded_frame(surface, pygame.Rect(150, 10, 120, 50), glow=0.8)
    decor.ornament_rule(surface, (200, 150), 200)
    decor.crown(surface, (200, 100), 60)
    decor.wood_tray(surface, pygame.Rect(10, 200, 200, 40))
    decor.scatter_sparkles(surface, surface.get_rect(), 1.0)
