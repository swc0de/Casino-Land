"""Procedurally drawn playing cards.

Everything is drawn with geometry at 3x size and smooth-scaled down, which gives
anti-aliased edges without any image assets. Court cards use original art-deco
crests (crowns, chevrons, a monogram band) rather than traditional artwork.
"""

from __future__ import annotations

import math

import pygame

from ...core.cards import Card, Rank, Suit
from .. import fonts, theme
from ..caches import optimise, surface_cache
from ..theme import Color

SS = 3  # supersampling factor
CARD_RATIO = 1.4  # height / width (poker size 2.5" x 3.5")

PAPER = (251, 248, 240)
PAPER_EDGE = (206, 198, 186)
INK_RED = (204, 22, 52)
INK_BLACK = (24, 22, 36)
GOLD = (214, 168, 58)
GOLD_DARK = (150, 110, 30)

# Pip positions for 2-10 as (x, y) in a unit box; y > 0.5 pips are drawn upside down.
PIP_LAYOUT: dict[int, tuple[tuple[float, float], ...]] = {
    2: ((0.5, 0.0), (0.5, 1.0)),
    3: ((0.5, 0.0), (0.5, 0.5), (0.5, 1.0)),
    4: ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)),
    5: ((0.0, 0.0), (1.0, 0.0), (0.5, 0.5), (0.0, 1.0), (1.0, 1.0)),
    6: ((0.0, 0.0), (1.0, 0.0), (0.0, 0.5), (1.0, 0.5), (0.0, 1.0), (1.0, 1.0)),
    7: ((0.0, 0.0), (1.0, 0.0), (0.5, 0.25), (0.0, 0.5), (1.0, 0.5), (0.0, 1.0), (1.0, 1.0)),
    8: (
        (0.0, 0.0),
        (1.0, 0.0),
        (0.5, 0.25),
        (0.0, 0.5),
        (1.0, 0.5),
        (0.5, 0.75),
        (0.0, 1.0),
        (1.0, 1.0),
    ),
    9: (
        (0.0, 0.0),
        (1.0, 0.0),
        (0.0, 1 / 3),
        (1.0, 1 / 3),
        (0.5, 0.5),
        (0.0, 2 / 3),
        (1.0, 2 / 3),
        (0.0, 1.0),
        (1.0, 1.0),
    ),
    10: (
        (0.0, 0.0),
        (1.0, 0.0),
        (0.5, 1 / 6),
        (0.0, 1 / 3),
        (1.0, 1 / 3),
        (0.0, 2 / 3),
        (1.0, 2 / 3),
        (0.5, 5 / 6),
        (0.0, 1.0),
        (1.0, 1.0),
    ),
}


def ink(suit: Suit) -> Color:
    return INK_RED if suit.is_red else INK_BLACK


def card_size(width: int) -> tuple[int, int]:
    return width, round(width * CARD_RATIO)


# -- suit shapes ----------------------------------------------------------------------


def draw_suit(
    surface: pygame.Surface,
    suit: Suit,
    center: tuple[float, float],
    size: float,
    color: Color,
) -> None:
    """Draw a suit symbol of height ``size`` centred on ``center``."""
    cx, cy = center
    s = size

    def p(x: float, y: float) -> tuple[float, float]:
        return cx + x * s, cy + y * s

    if suit is Suit.HEARTS:
        r = 0.27 * s
        pygame.draw.circle(surface, color, p(-0.23, -0.17), r)
        pygame.draw.circle(surface, color, p(0.23, -0.17), r)
        pygame.draw.polygon(surface, color, [p(-0.49, -0.08), p(0.49, -0.08), p(0.0, 0.5)])
        pygame.draw.polygon(surface, color, [p(-0.25, -0.3), p(0.25, -0.3), p(0.0, 0.0)])
    elif suit is Suit.DIAMONDS:
        points = []
        for i in range(48):
            a = i / 48 * math.tau
            # Diamond with gently pinched sides, like a printed card.
            x, y = math.sin(a), -math.cos(a)
            k = 1.0 / (abs(x) + abs(y)) ** 0.85
            points.append(p(0.4 * x * k, 0.5 * y * k))
        pygame.draw.polygon(surface, color, points)
    elif suit is Suit.SPADES:
        r = 0.255 * s
        pygame.draw.circle(surface, color, p(-0.22, 0.08), r)
        pygame.draw.circle(surface, color, p(0.22, 0.08), r)
        pygame.draw.polygon(surface, color, [p(-0.47, 0.0), p(0.47, 0.0), p(0.0, -0.5)])
        pygame.draw.polygon(surface, color, [p(-0.24, 0.2), p(0.24, 0.2), p(0.0, -0.1)])
        pygame.draw.polygon(surface, color, [p(0.0, 0.1), p(-0.17, 0.5), p(0.17, 0.5)])
    else:  # clubs
        r = 0.21 * s
        pygame.draw.circle(surface, color, p(0.0, -0.25), r)
        pygame.draw.circle(surface, color, p(-0.24, 0.07), r)
        pygame.draw.circle(surface, color, p(0.24, 0.07), r)
        pygame.draw.circle(surface, color, p(0.0, 0.0), r * 0.6)
        pygame.draw.polygon(surface, color, [p(0.0, -0.02), p(-0.16, 0.5), p(0.16, 0.5)])


@surface_cache(maxsize=128)
def suit_icon(suit: Suit, size: int, color: Color | None = None) -> pygame.Surface:
    """An anti-aliased suit symbol for UI labels."""
    big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    draw_suit(big, suit, (size * SS / 2, size * SS / 2), size * SS * 0.92, color or ink(suit))
    return pygame.transform.smoothscale(big, (size, size))


# -- card faces -----------------------------------------------------------------------


def _paper(w: int, h: int, corner: int) -> pygame.Surface:
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, PAPER_EDGE, surf.get_rect(), border_radius=corner)
    pygame.draw.rect(surf, PAPER, surf.get_rect().inflate(-2 * SS, -2 * SS), border_radius=corner)
    # Very soft vertical sheen so the card doesn't look flat.
    sheen = pygame.Surface((w, h // 2), pygame.SRCALPHA)
    for y in range(0, h // 2, SS):
        a = round(16 * (1 - y / (h / 2)))
        pygame.draw.line(sheen, (255, 255, 255, a), (0, y), (w, y), SS)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
    sheen_full = pygame.Surface((w, h), pygame.SRCALPHA)
    sheen_full.blit(sheen, (0, 0))
    sheen_full.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(sheen_full, (0, 0))
    return surf


def _corner_index(card: Card, w: int, h: int) -> pygame.Surface:
    color = ink(card.suit)
    rank_font = fonts.get("body_bold", round(h * 0.19))
    label = rank_font.render(card.rank.label, True, color)
    if card.rank is Rank.TEN:
        label = pygame.transform.smoothscale(
            label, (round(label.get_width() * 0.82), label.get_height())
        )
    box_w = max(label.get_width(), round(w * 0.16))
    pip = round(w * 0.13)
    surf = pygame.Surface((box_w, round(label.get_height() * 0.82) + pip), pygame.SRCALPHA)
    surf.blit(label, label.get_rect(midtop=(box_w / 2, -round(h * 0.012))))
    draw_suit(surf, card.suit, (box_w / 2, label.get_height() * 0.82 + pip / 2 - SS), pip, color)
    return surf


def _pips(surface: pygame.Surface, card: Card, w: int, h: int) -> None:
    color = ink(card.suit)
    left, right = w * 0.3, w * 0.7
    top, bottom = h * 0.21, h * 0.79
    size = w * 0.2
    for ux, uy in PIP_LAYOUT[int(card.rank)]:
        x = left + (right - left) * ux
        y = top + (bottom - top) * uy
        if uy > 0.5 and card.suit is not Suit.DIAMONDS:
            pip = pygame.Surface((round(size * 1.2), round(size * 1.2)), pygame.SRCALPHA)
            draw_suit(pip, card.suit, (pip.get_width() / 2, pip.get_height() / 2), size, color)
            pip = pygame.transform.rotate(pip, 180)
            surface.blit(pip, pip.get_rect(center=(x, y)))
        else:
            draw_suit(surface, card.suit, (x, y), size, color)


def _ace(surface: pygame.Surface, card: Card, w: int, h: int) -> None:
    color = ink(card.suit)
    c = (w / 2, h / 2)
    if card.suit is Suit.SPADES:
        # The ace of spades traditionally gets the ornate treatment.
        pygame.draw.circle(surface, GOLD, c, w * 0.34, round(SS * 2.2))
        pygame.draw.circle(surface, GOLD, c, w * 0.3, SS)
        for i in range(16):
            a = i / 16 * math.tau
            x, y = c[0] + math.cos(a) * w * 0.37, c[1] + math.sin(a) * w * 0.37
            pygame.draw.circle(surface, GOLD, (x, y), SS * 2.2)
        draw_suit(surface, card.suit, c, w * 0.42, color)
    else:
        draw_suit(surface, card.suit, c, w * 0.46, color)


def _crown(surf: pygame.Surface, cx: float, base_y: float, width: float, points: int) -> None:
    height = width * 0.62
    left, right = cx - width / 2, cx + width / 2
    outline = [(left, base_y)]
    for i in range(points * 2 + 1):
        x = left + width * i / (points * 2)
        y = base_y - height if i % 2 == 0 else base_y - height * 0.45
        outline.append((x, y))
    outline.append((right, base_y))
    pygame.draw.polygon(surf, GOLD, outline)
    pygame.draw.polygon(surf, GOLD_DARK, outline, SS)
    band = pygame.Rect(left, base_y - height * 0.22, width, height * 0.22)
    pygame.draw.rect(surf, GOLD_DARK, band)
    for i in range(points + 1):
        x = left + width * i / points
        pygame.draw.circle(surf, theme.WARM_WHITE, (x, base_y - height), width * 0.05)


def _court_half(card: Card, w: int, h: int) -> pygame.Surface:
    """Top half of a double-ended court card; the bottom half is this rotated 180°."""
    color = ink(card.suit)
    half = pygame.Surface((w, h // 2), pygame.SRCALPHA)
    cx = w / 2
    letter_font = fonts.get("display", round(h * 0.17))
    if card.rank is Rank.KING:
        _crown(half, cx, h * 0.27, w * 0.28, 3)
    elif card.rank is Rank.QUEEN:
        _crown(half, cx, h * 0.265, w * 0.26, 5)
        pygame.draw.circle(half, color, (cx, h * 0.215), w * 0.03)
    else:
        # Jack: stacked art-deco chevrons.
        for i in range(3):
            y = h * 0.155 + i * h * 0.035
            pts = [(cx - w * 0.17, y), (cx, y + h * 0.045), (cx + w * 0.17, y)]
            pygame.draw.lines(half, GOLD if i != 1 else color, False, pts, round(SS * 3))
    letter = letter_font.render(card.rank.label, True, color)
    half.blit(letter, letter.get_rect(center=(cx, h * 0.385)))
    draw_suit(half, card.suit, (w * 0.32, h * 0.385), w * 0.09, color)
    draw_suit(half, card.suit, (w * 0.68, h * 0.385), w * 0.09, color)
    return half


def _court(surface: pygame.Surface, card: Card, w: int, h: int) -> None:
    color = ink(card.suit)
    frame = pygame.Rect(round(w * 0.215), round(h * 0.11), round(w * 0.57), round(h * 0.78))
    wash = (252, 232, 238) if card.suit.is_red else (232, 232, 246)
    pygame.draw.rect(surface, wash, frame, border_radius=SS * 4)
    pygame.draw.rect(surface, color, frame, SS * 2, border_radius=SS * 4)
    pygame.draw.rect(surface, GOLD, frame.inflate(-SS * 5, -SS * 5), SS, border_radius=SS * 3)

    clip = surface.get_clip()
    surface.set_clip(frame.inflate(-SS * 6, -SS * 6))
    half = _court_half(card, w, h)
    surface.blit(half, (0, 0))
    surface.blit(pygame.transform.rotate(half, 180), (0, h // 2))
    surface.set_clip(clip)
    # Diagonal band through the middle, as on a real double-ended court card.
    mid = h / 2
    pygame.draw.line(
        surface,
        color,
        (frame.left + SS * 4, mid + h * 0.04),
        (frame.right - SS * 4, mid - h * 0.04),
        SS * 2,
    )


@surface_cache(maxsize=160)
def card_face(card: Card, width: int) -> pygame.Surface:
    out_w, out_h = card_size(width)
    w, h = out_w * SS, out_h * SS
    corner = round(w * 0.075)
    surf = _paper(w, h, corner)

    if card.rank is Rank.ACE:
        _ace(surf, card, w, h)
    elif card.rank.is_face:
        _court(surf, card, w, h)
    else:
        _pips(surf, card, w, h)

    index = _corner_index(card, w, h)
    surf.blit(index, (round(w * 0.04), round(h * 0.035)))
    flipped = pygame.transform.rotate(index, 180)
    surf.blit(flipped, flipped.get_rect(bottomright=(w - round(w * 0.04), h - round(h * 0.035))))

    small = pygame.transform.smoothscale(surf, (out_w, out_h))
    return optimise(small)


BACK_RED = (168, 18, 34)


@surface_cache(maxsize=16)
def card_back(width: int, color: Color = BACK_RED) -> pygame.Surface:
    """A classic casino card back: fine lattice on ivory inside a coloured frame."""
    out_w, out_h = card_size(width)
    w, h = out_w * SS, out_h * SS
    corner = round(w * 0.075)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rect = surf.get_rect()
    pygame.draw.rect(surf, PAPER, rect, border_radius=corner)
    inner = rect.inflate(-round(w * 0.1), -round(w * 0.1))
    pygame.draw.rect(surf, color, inner, border_radius=corner // 2)

    # Diamond lattice in ivory over the coloured field.
    field = inner.inflate(-SS * 8, -SS * 8)
    pattern = pygame.Surface(field.size, pygame.SRCALPHA)
    step = round(w * 0.085)
    ivory = (250, 240, 222, 210)
    for i in range(-field.height // step - 2, field.width // step + 3):
        x = i * step
        pygame.draw.line(pattern, ivory, (x, 0), (x + field.height, field.height), SS)
        pygame.draw.line(pattern, ivory, (x, 0), (x - field.height, field.height), SS)
    for i in range(-field.height // step - 2, field.width // step + 3):
        for j in range(0, field.height // step + 2):
            pygame.draw.circle(pattern, ivory, (i * step + step / 2 + j * 0, j * step), SS * 1.4)
    surf.blit(pattern, field.topleft)
    pygame.draw.rect(surf, PAPER, field, SS * 2, border_radius=corner // 3)
    pygame.draw.rect(surf, color, field.inflate(SS * 4, SS * 4), SS, border_radius=corner // 3)

    # Central medallion with a gold crown-spade.
    c = rect.center
    pygame.draw.ellipse(surf, PAPER, pygame.Rect(0, 0, w * 0.46, w * 0.62).move(
        c[0] - w * 0.23, c[1] - w * 0.31))  # fmt: skip
    pygame.draw.ellipse(surf, color, pygame.Rect(0, 0, w * 0.4, w * 0.56).move(
        c[0] - w * 0.2, c[1] - w * 0.28), SS * 2)  # fmt: skip
    draw_suit(surf, Suit.SPADES, (c[0], c[1] + w * 0.02), w * 0.22, GOLD_DARK)
    draw_suit(surf, Suit.SPADES, (c[0], c[1]), w * 0.22, GOLD)
    small = pygame.transform.smoothscale(surf, (out_w, out_h))
    return optimise(small)


@surface_cache(maxsize=16)
def card_shadow(width: int, spread: int = 6) -> pygame.Surface:
    out_w, out_h = card_size(width)
    surf = pygame.Surface((out_w + spread * 4, out_h + spread * 4), pygame.SRCALPHA)
    pygame.draw.rect(
        surf,
        (0, 0, 0, 150),
        surf.get_rect().inflate(-spread * 4, -spread * 4),
        border_radius=round(out_w * 0.075),
    )
    for _ in range(3):
        surf = pygame.transform.box_blur(surf, max(1, spread // 2))
    return surf
