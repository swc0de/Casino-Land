"""Casino furnishings drawn in code: engraved gold lettering, gilded frames, brass
plaques, polished wood, padded leather, velvet, ornate carpet and pools of light.

Everything expensive is built once and cached; per frame we only blit.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from .. import fonts, theme
from ..caches import optimise, surface_cache
from ..fx.glow import pad, soft_blur, tint
from ..theme import Color, lerp_color, scale_color
from .backdrop import add_grain, add_vignette, to_surface

SS = 2

# Metallic ramps: colours from the top of a letter to the bottom.
GOLD_RAMP: tuple[Color, ...] = ((255, 240, 180), (236, 196, 96), (178, 128, 40), (232, 190, 92))
CREAM_RAMP: tuple[Color, ...] = ((255, 250, 236), (244, 232, 204), (214, 196, 160), (240, 226, 196))
SILVER_RAMP: tuple[Color, ...] = (
    (255, 255, 255),
    (214, 214, 222),
    (140, 140, 152),
    (206, 206, 214),
)
RUBY_RAMP: tuple[Color, ...] = ((255, 150, 140), (226, 60, 60), (140, 14, 24), (210, 54, 54))
EMERALD_RAMP: tuple[Color, ...] = ((200, 255, 200), (110, 220, 120), (30, 120, 50), (100, 200, 110))

RAMPS = {
    "gold": GOLD_RAMP,
    "cream": CREAM_RAMP,
    "silver": SILVER_RAMP,
    "ruby": RUBY_RAMP,
    "emerald": EMERALD_RAMP,
}


def _ramp_surface(size: tuple[int, int], ramp: tuple[Color, ...]) -> pygame.Surface:
    w, h = size
    stops = np.linspace(0.0, 1.0, len(ramp))
    ys = np.linspace(0.0, 1.0, max(1, h))
    rgb = np.stack([np.interp(ys, stops, [c[i] for c in ramp]) for i in range(3)], axis=1)
    column = np.repeat(rgb[None, :, :], max(1, w), axis=0)  # (w, h, 3)
    return _with_alpha(pygame.surfarray.make_surface(column.astype(np.uint8)))


def _with_alpha(surf: pygame.Surface) -> pygame.Surface:
    out = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    out.blit(surf, (0, 0))
    return out


def metallic(mask: pygame.Surface, ramp: tuple[Color, ...]) -> pygame.Surface:
    """Fill a white-on-transparent mask with a vertical metallic gradient."""
    face = _ramp_surface(mask.get_size(), ramp)
    face.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return face


class Engraved:
    """Lettering or an emblem with a metallic face, dark rim, bevel and drop shadow."""

    def __init__(
        self,
        mask: pygame.Surface,
        ramp: tuple[Color, ...] = GOLD_RAMP,
        outline: Color = (40, 22, 6),
        shadow: int = 3,
        glow: float = 0.0,
        glow_color: Color = theme.GOLD,
    ) -> None:
        margin = max(6, shadow * 3, 14 if glow else 0)
        m = pad(mask, margin)
        self.margin = margin
        size = m.get_size()
        out = pygame.Surface(size, pygame.SRCALPHA)
        if glow:
            halo = soft_blur(tint(m, glow_color), max(4, margin // 2))
            halo.set_alpha(round(200 * glow))
            out.blit(halo, (0, 0))
        if shadow:
            drop = soft_blur(tint(m, (0, 0, 0)), max(1, shadow // 2 + 1))
            drop.set_alpha(190)
            out.blit(drop, (shadow // 2 + 1, shadow))
        rim = tint(m, outline)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (1, -1), (-1, 1)):
            out.blit(rim, (dx, dy))
        light = tint(m, lerp_color(ramp[0], (255, 255, 255), 0.5))
        light.set_alpha(150)
        out.blit(light, (0, -1))
        out.blit(metallic(m, ramp), (0, 0))
        self.surface = optimise(out)
        self.size = size

    @property
    def content_size(self) -> tuple[int, int]:
        return self.size[0] - 2 * self.margin, self.size[1] - 2 * self.margin

    def draw(
        self, surface: pygame.Surface, center: tuple[float, float], alpha: float = 1.0
    ) -> pygame.Rect:
        rect = self.surface.get_rect(center=(round(center[0]), round(center[1])))
        if alpha <= 0.01:
            return rect
        if alpha < 0.99:
            self.surface.set_alpha(round(255 * alpha))
            surface.blit(self.surface, rect)
            self.surface.set_alpha(255)
        else:
            surface.blit(self.surface, rect)
        return rect


@surface_cache(maxsize=256)
def engraved_text(
    text: str,
    role: str = "display",
    size: int = 32,
    style: str = "gold",
    glow: float = 0.0,
    shadow: int = 3,
) -> Engraved:
    """Gold-leaf (or cream, silver, ruby, emerald) lettering, cached."""
    mask = fonts.get(role, size).render(text, True, (255, 255, 255))
    glow_color = {"ruby": (255, 60, 60), "emerald": (90, 230, 110)}.get(style, theme.GOLD)
    return Engraved(mask, RAMPS[style], shadow=shadow, glow=glow, glow_color=glow_color)


# -- frames and plates ------------------------------------------------------------------


@surface_cache(maxsize=96)
def gilded_frame(
    size: tuple[int, int], width: int = 4, radius: int = 12, glow: float = 0.0
) -> pygame.Surface:
    """A gold moulding: dark outer edge, bright bevel, gold body. Transparent inside."""
    w, h = size
    margin = 16 if glow else 2
    out = pygame.Surface((w + 2 * margin, h + 2 * margin), pygame.SRCALPHA)
    rect = pygame.Rect(margin, margin, w, h)
    if glow:
        halo = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*theme.GOLD_LIGHT, 255), rect, width + 4, border_radius=radius)
        halo = soft_blur(halo, 8)
        halo.set_alpha(round(220 * glow))
        out.blit(halo, (0, 0))
    mask = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255), rect, width, border_radius=radius)
    out.blit(tint(mask, (50, 30, 8)), (1, 1))
    out.blit(metallic(mask, GOLD_RAMP), (0, 0))
    inner = rect.inflate(-2 * width + 2, -2 * width + 2)
    if inner.width > 0 and inner.height > 0:
        pygame.draw.rect(
            out, (*theme.GOLD_LIGHT, 200), rect.inflate(-2, -2), 1, border_radius=max(0, radius - 1)
        )
    return optimise(out)


def draw_gilded_frame(
    surface: pygame.Surface,
    rect: pygame.Rect,
    width: int = 4,
    radius: int = 12,
    glow: float = 0.0,
) -> None:
    frame = gilded_frame(rect.size, width, radius, round(glow, 1))
    surface.blit(frame, frame.get_rect(center=rect.center))


def lacquer_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    base: Color = (22, 12, 8),
    alpha: int = 238,
    border: bool = True,
    radius: int = 14,
    glow: float = 0.0,
) -> None:
    """A polished dark panel (walnut lacquer) with a gold trim."""
    panel = _panel_fill(rect.size, base, radius)
    panel.set_alpha(alpha)
    surface.blit(panel, rect)
    if border:
        draw_gilded_frame(surface, rect, 3, radius, glow)


@surface_cache(maxsize=96)
def _panel_fill(size: tuple[int, int], base: Color, radius: int) -> pygame.Surface:
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    top = lerp_color(base, (255, 230, 190), 0.10)
    for y in range(h):
        k = y / max(1, h - 1)
        pygame.draw.line(surf, lerp_color(top, base, min(1.0, k * 1.6)), (0, y), (w, y))
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


@surface_cache(maxsize=48)
def brass_plaque(size: tuple[int, int], text: str = "", text_size: int = 22) -> pygame.Surface:
    """A screwed-on brass name plate with engraved lettering."""
    w, h = size
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    r = pygame.Rect(0, 0, w * SS, h * SS)
    pygame.draw.rect(big, (70, 46, 14), r, border_radius=10 * SS)
    face = _ramp_surface(
        r.inflate(-4 * SS, -4 * SS).size,
        ((250, 220, 140), (206, 160, 70), (150, 104, 36), (196, 150, 64)),
    )
    mask = pygame.Surface(face.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=8 * SS)
    face.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    big.blit(face, (2 * SS, 2 * SS))
    for x in (9 * SS, w * SS - 9 * SS):
        c = (x, h * SS // 2)
        pygame.draw.circle(big, (90, 60, 20), c, 4 * SS)
        pygame.draw.circle(big, (240, 210, 140), c, 4 * SS - 2)
        pygame.draw.line(big, (90, 60, 20), (c[0] - 3 * SS, c[1]), (c[0] + 3 * SS, c[1]), SS)
    plate = pygame.transform.smoothscale(big, size)
    if text:
        font = fonts.get("display", text_size)
        dark = font.render(text, True, (52, 30, 8))
        light = font.render(text, True, (255, 236, 180))
        cx, cy = w // 2, h // 2
        plate.blit(light, light.get_rect(center=(cx, cy + 1)))
        plate.blit(dark, dark.get_rect(center=(cx, cy)))
    return optimise(plate)


# -- materials ------------------------------------------------------------------------


@surface_cache(maxsize=16)
def wood(
    size: tuple[int, int], tone: Color = theme.MAHOGANY, seed: int = 4, vertical: bool = False
) -> pygame.Surface:
    """Polished wood with flowing grain and a lacquer sheen."""
    w, h = size
    rng = np.random.default_rng(seed)
    if vertical:
        w, h = h, w
    x = np.arange(w)[None, :]
    y = np.arange(h)[:, None]
    warp = np.sin(x * 0.012 + rng.uniform(0, 6)) * 6 + np.sin(x * 0.047) * 2
    rings = np.sin((y + warp) * 0.21 + np.sin(x * 0.006) * 3) * 0.5 + 0.5
    streaks = np.sin(y * 1.7 + np.sin(x * 0.02) * 2) * 0.5 + 0.5
    fine = rng.normal(0, 1, (h, w)) * 0.035
    k = 0.8 + 0.13 * rings + 0.05 * streaks + fine
    base = np.array(tone, dtype=float)
    rgb = base[None, None, :] * k[:, :, None]
    sheen = np.exp(-(((y / max(1, h)) - 0.3) ** 2) / 0.02) * 26
    rgb = rgb + sheen[:, :, None]
    if vertical:
        rgb = rgb.transpose(1, 0, 2)
    return to_surface(rgb)


@surface_cache(maxsize=8)
def carpet(size: tuple[int, int] = theme.SIZE, seed: int = 7, dim: float = 1.0) -> pygame.Surface:
    """Ornate casino carpet: gold medallions and teal diamonds on deep burgundy."""
    tile = _carpet_tile(128)
    w, h = size
    surf = pygame.Surface(size)
    for ty in range(0, h + 128, 128):
        for tx in range(0, w + 128, 128):
            surf.blit(tile, (tx - 32, ty - 32))
    rgb = pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(float)
    add_grain(rgb, 7.0, seed)
    rgb *= dim
    return to_surface(add_vignette(rgb, 0.55))


def _carpet_tile(size: int) -> pygame.Surface:
    s = size * SS
    tile = pygame.Surface((s, s))
    tile.fill(theme.CARPET)
    c = s / 2
    gold = (186, 140, 52)
    teal = (18, 76, 78)
    navy = (22, 26, 58)
    dark = theme.CARPET_DARK
    # Corner diamonds (shared by four tiles).
    for cx, cy in ((0, 0), (s, 0), (0, s), (s, s)):
        pts = [(cx, cy - s * 0.22), (cx + s * 0.22, cy), (cx, cy + s * 0.22), (cx - s * 0.22, cy)]
        pygame.draw.polygon(tile, navy, pts)
        pygame.draw.polygon(tile, gold, pts, SS * 2)
        pygame.draw.circle(tile, gold, (cx, cy), s * 0.05)
    # Central medallion: eight petals inside a ring.
    pygame.draw.circle(tile, dark, (c, c), s * 0.3)
    for i in range(8):
        a = i * math.tau / 8
        px, py = c + math.cos(a) * s * 0.17, c + math.sin(a) * s * 0.17
        pygame.draw.circle(tile, teal, (px, py), s * 0.075)
        pygame.draw.circle(tile, gold, (px, py), s * 0.075, SS * 2)
    pygame.draw.circle(tile, gold, (c, c), s * 0.3, SS * 3)
    pygame.draw.circle(tile, gold, (c, c), s * 0.08)
    pygame.draw.circle(tile, dark, (c, c), s * 0.04)
    # Scroll dots between motifs.
    for i in range(4):
        a = i * math.tau / 4 + math.pi / 4
        for r, rad in ((0.4, 0.022), (0.46, 0.014)):
            pygame.draw.circle(
                tile, gold, (c + math.cos(a) * s * r, c + math.sin(a) * s * r), s * rad
            )
    for edge in ((c, 0), (c, s), (0, c), (s, c)):
        pygame.draw.circle(tile, teal, edge, s * 0.06)
        pygame.draw.circle(tile, gold, edge, s * 0.06, SS)
    return pygame.transform.smoothscale(tile, (size, size))


@surface_cache(maxsize=4)
def velvet(size: tuple[int, int] = theme.SIZE, seed: int = 2) -> pygame.Surface:
    """Deep red velvet curtain with soft folds and a warm spotlight."""
    w, h = size
    rng = np.random.default_rng(seed)
    x = np.arange(w)[None, :].astype(float)
    y = np.arange(h)[:, None].astype(float)
    folds = np.zeros((1, w))
    for freq, amp in ((0.021, 0.5), (0.047, 0.25), (0.009, 0.25)):
        folds = folds + amp * np.sin(x * freq + rng.uniform(0, 6))
    shade = 0.55 + 0.45 * (folds * 0.5 + 0.5) ** 1.4
    base = np.array(theme.VELVET, dtype=float)
    rgb = base[None, None, :] * shade[:, :, None] * np.ones((h, 1, 1))
    spot = np.exp(-(((x - w / 2) / (w * 0.42)) ** 2 + ((y - h * 0.42) / (h * 0.62)) ** 2))
    rgb = rgb * (0.35 + 0.85 * spot[:, :, None])
    add_grain(rgb, 3.0, seed)
    return to_surface(add_vignette(rgb, 0.4))


@surface_cache(maxsize=16)
def light_pool(
    size: tuple[int, int], color: Color = (255, 214, 150), strength: int = 90
) -> pygame.Surface:
    """A soft elliptical pool of warm light (from a pendant lamp above)."""
    w, h = size
    y = np.linspace(-1, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    a = np.clip(1 - (x * x + y * y), 0, 1) ** 1.8 * strength
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pixels = pygame.surfarray.pixels3d(surf)
    pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2] = color
    del pixels
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:, :] = a.T.astype(np.uint8)
    del alpha
    return surf


def padded_ellipse(
    surface: pygame.Surface,
    rect: pygame.Rect,
    thickness: int,
    base: Color = theme.LEATHER,
    hi: Color = theme.LEATHER_HI,
) -> None:
    """A padded leather armrest running round an oval table."""
    steps = max(6, thickness)
    for i in range(steps):
        k = i / (steps - 1)
        profile = math.sin(k * math.pi) ** 0.6
        light = max(0.0, math.cos((k - 0.32) * math.pi)) ** 3
        color = lerp_color(scale_color(base, 0.6 + 0.4 * profile), hi, light * 0.55)
        inset = round(thickness * k)
        pygame.draw.ellipse(
            surface,
            color,
            rect.inflate(-2 * inset, -2 * inset),
            max(2, round(thickness / steps) + 1),
        )


def padded_band(
    surface: pygame.Surface,
    rect: pygame.Rect,
    base: Color = theme.LEATHER,
    hi: Color = theme.LEATHER_HI,
) -> None:
    """A straight padded leather rail (vertical profile across its height)."""
    for y in range(rect.height):
        k = y / max(1, rect.height - 1)
        profile = math.sin(k * math.pi) ** 0.6
        light = max(0.0, math.cos((k - 0.3) * math.pi)) ** 3
        color = lerp_color(scale_color(base, 0.6 + 0.4 * profile), hi, light * 0.55)
        pygame.draw.line(surface, color, (rect.left, rect.top + y), (rect.right, rect.top + y))


def ornament_rule(surface: pygame.Surface, center: tuple[int, int], width: int) -> None:
    """A thin gold rule with a diamond in the middle: ——◆——."""
    cx, cy = center
    gold = theme.GOLD
    pygame.draw.line(surface, gold, (cx - width // 2, cy), (cx - 14, cy), 2)
    pygame.draw.line(surface, gold, (cx + 14, cy), (cx + width // 2, cy), 2)
    pygame.draw.polygon(
        surface, theme.GOLD_LIGHT, [(cx, cy - 7), (cx + 8, cy), (cx, cy + 7), (cx - 8, cy)]
    )
    for side in (-1, 1):
        pygame.draw.circle(surface, gold, (cx + side * (width // 2 + 6), cy), 3)


def crown(surface: pygame.Surface, center: tuple[float, float], width: float) -> None:
    """A small jewelled crown emblem in gold."""
    if width < 4:
        return
    image = _crown_image(round(width))
    surface.blit(image, image.get_rect(center=(round(center[0]), round(center[1]))))


@surface_cache(maxsize=128)
def _crown_image(width: int) -> pygame.Surface:
    w = width * SS
    h = w * 0.62
    pad_ = 4 * SS
    big = pygame.Surface((round(w + 2 * pad_), round(h + 2 * pad_)), pygame.SRCALPHA)
    left, top = pad_, pad_
    base = top + h
    band = h * 0.24
    peaks = [(0.0, 0.0), (0.25, 0.45), (0.5, -0.08), (0.75, 0.45), (1.0, 0.0)]
    outline = [(left, base - band)]
    outline += [(left + w * fx, top + h * 0.12 + (h - band) * fy * 0.9) for fx, fy in peaks]
    outline += [(left + w, base - band), (left + w, base), (left, base)]
    pygame.draw.polygon(big, (255, 255, 255), outline)
    mask = pygame.transform.smoothscale(big, (big.get_width() // SS, big.get_height() // SS))
    emblem = Engraved(mask, GOLD_RAMP, shadow=2)
    out = emblem.surface.copy()
    cx, cy = out.get_width() / 2, out.get_height() / 2
    hh, bb = h / SS, band / SS
    jewel_y = cy + hh / 2 - bb / 2
    for fx, color in ((0.25, (40, 120, 210)), (0.5, (210, 30, 44)), (0.75, (40, 120, 210))):
        pygame.draw.circle(
            out, color, (cx - width / 2 + width * fx, jewel_y), max(2, width * 0.045)
        )
    for fx in (0.0, 0.5, 1.0):
        x = cx - width / 2 + width * fx
        lift = 0.08 * 0.9 * (hh - bb) if fx == 0.5 else 0
        y = cy - hh / 2 + hh * 0.12 - lift
        pygame.draw.circle(out, theme.WARM_WHITE, (x, y), max(2, width * 0.05))
    return out


def scatter_sparkles(
    surface: pygame.Surface, rect: pygame.Rect, t: float, count: int = 12, seed: int = 1
) -> None:
    """Glints of light twinkling across polished brass or crystal."""
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.uniform(rect.left, rect.right)
        y = rng.uniform(rect.top, rect.bottom)
        phase = rng.uniform(0, math.tau)
        k = max(0.0, math.sin(t * rng.uniform(0.8, 1.6) + phase)) ** 6
        if k < 0.05:
            continue
        r = 2 + 6 * k
        color = (255, 246, 214)
        pygame.draw.line(surface, color, (x - r, y), (x + r, y), 1)
        pygame.draw.line(surface, color, (x, y - r), (x, y + r), 1)
        pygame.draw.circle(surface, color, (x, y), 1 + k * 1.5)


@surface_cache(maxsize=6)
def table_background(
    felt_color: Color = theme.FELT_GREEN,
    felt_dark: Color = theme.FELT_GREEN_DARK,
    seed: int = 1,
    rail: int = 26,
) -> pygame.Surface:
    """A whole-screen gaming table: baize framed by a polished mahogany rail."""
    from .backdrop import felt

    w, h = theme.SIZE
    surf = felt(theme.SIZE, felt_color, felt_dark, seed).copy()
    frame = wood(theme.SIZE, theme.MAHOGANY, seed + 20)
    mask = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    mask.fill((255, 255, 255, 255))
    pygame.draw.rect(
        mask, (0, 0, 0, 0), pygame.Rect(rail, rail, w - 2 * rail, h - 2 * rail), border_radius=18
    )
    rim = frame.convert_alpha()
    rim.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    # Shadow the felt where the rail overhangs it.
    shade = pygame.Surface(theme.SIZE, pygame.SRCALPHA)
    pygame.draw.rect(
        shade,
        (0, 0, 0, 160),
        pygame.Rect(rail - 6, rail - 6, w - 2 * rail + 12, h - 2 * rail + 12),
        14,
        border_radius=22,
    )
    surf.blit(soft_blur(shade, 8), (0, 0))
    surf.blit(rim, (0, 0))
    inner = pygame.Rect(rail, rail, w - 2 * rail, h - 2 * rail)
    pygame.draw.rect(surf, theme.GOLD_DARK, inner.inflate(4, 4), 2, border_radius=19)
    pygame.draw.rect(surf, theme.GOLD, inner.inflate(10, 10), 1, border_radius=22)
    pygame.draw.rect(surf, (20, 8, 4), surf.get_rect(), 3)
    return surf


def wood_tray(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """A recessed wooden chip tray."""
    surface.blit(wood(rect.size, theme.WALNUT, rect.width), rect)
    pygame.draw.rect(surface, (10, 4, 2), rect, 3, border_radius=10)
    pygame.draw.rect(surface, theme.GOLD_DARK, rect.inflate(4, 4), 2, border_radius=12)
