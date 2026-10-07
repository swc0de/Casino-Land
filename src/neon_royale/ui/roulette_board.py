"""Geometry of the roulette betting layout: where every bet sits and hit-testing.

The layout is drawn as the player sees it: zero on the left, three rows of numbers
(3, 6, 9 … along the top; 1, 4, 7 … along the bottom), the 2:1 column boxes on the
right, dozens and even-money boxes underneath. Chips on a line or corner between
numbers make split, street, corner, trio, six-line and first-four bets.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..core import roulette as r
from ..core.roulette import Bet, BetKind

EDGE = 0.24  # fraction of a cell, from a line, that counts as "on the line"


@dataclass
class BoardGeometry:
    left: int  # x of the zero box
    top: int
    cell_w: int = 54
    cell_h: int = 66
    band_h: int = 46  # dozens and even-money rows

    @property
    def grid_left(self) -> int:
        return self.left + self.cell_w

    @property
    def grid_rect(self) -> pygame.Rect:
        return pygame.Rect(self.grid_left, self.top, 12 * self.cell_w, 3 * self.cell_h)

    @property
    def zero_rect(self) -> pygame.Rect:
        return pygame.Rect(self.left, self.top, self.cell_w, 3 * self.cell_h)

    @property
    def rect(self) -> pygame.Rect:
        width = 14 * self.cell_w
        height = 3 * self.cell_h + 2 * self.band_h
        return pygame.Rect(self.left, self.top, width, height)

    def cell_rect(self, number: int) -> pygame.Rect:
        if number == 0:
            return self.zero_rect
        street, row = r.street_of(number), r.row_of(number)
        return pygame.Rect(
            self.grid_left + street * self.cell_w,
            self.top + (2 - row) * self.cell_h,
            self.cell_w,
            self.cell_h,
        )

    def column_rect(self, row: int) -> pygame.Rect:
        return pygame.Rect(
            self.grid_left + 12 * self.cell_w,
            self.top + (2 - row) * self.cell_h,
            self.cell_w,
            self.cell_h,
        )

    def dozen_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(
            self.grid_left + index * 4 * self.cell_w,
            self.top + 3 * self.cell_h,
            4 * self.cell_w,
            self.band_h,
        )

    def outside_rects(self) -> list[tuple[Bet, pygame.Rect]]:
        bets = [r.low(), r.even(), r.red(), r.black(), r.odd(), r.high()]
        y = self.top + 3 * self.cell_h + self.band_h
        return [
            (
                bet,
                pygame.Rect(self.grid_left + i * 2 * self.cell_w, y, 2 * self.cell_w, self.band_h),
            )
            for i, bet in enumerate(bets)
        ]

    def box_bets(self) -> list[tuple[Bet, pygame.Rect]]:
        """Bets made by putting chips inside a box (not on a line)."""
        boxes = [(r.column(row), self.column_rect(row)) for row in range(3)]
        boxes += [(r.dozen(i), self.dozen_rect(i)) for i in range(3)]
        return boxes + self.outside_rects()

    # -- hit testing --------------------------------------------------------------------

    def bet_at(self, pos: tuple[int, int]) -> Bet | None:
        x, y = pos
        for bet, rect in self.box_bets():
            # The top strip of the dozens row belongs to the street/six-line lines.
            if bet.kind is BetKind.DOZEN and y < rect.top + EDGE * self.cell_h:
                continue
            if rect.collidepoint(pos):
                return bet
        fx = (x - self.grid_left) / self.cell_w
        fy = (y - self.top) / self.cell_h
        if not (-EDGE <= fx <= 12 and 0 <= fy <= 3 + EDGE):
            return straight_zero if self.zero_rect.collidepoint(pos) else None
        k = round(fx)
        j = round(fy)
        near_v = abs(fx - k) < EDGE and 0 <= k <= 11
        near_h = abs(fy - j) < EDGE and 1 <= j <= 3
        if fy > 3:  # just below the grid: only lines count there
            near_h, j = True, 3
        street = min(11, max(0, int(fx)))
        t = min(2, max(0, int(fy)))  # row counted from the top
        if near_v and near_h:
            if k == 0:
                return r.first_four() if j == 3 else r.trio(3 if j == 1 else 1)
            if j == 3:
                return r.six_line(k - 1)
            return r.corner(3 * (k - 1) + (2 - j) + 1)
        if near_v:
            number = 3 * k + (2 - t) + 1 if k < 12 else None
            if k == 0:
                return r.split(0, 3 - t)
            return r.split(number - 3, number) if number else None
        if near_h:
            if j == 3:
                return r.street(street)
            low = 3 * street + (2 - j) + 1
            return r.split(low, low + 1)
        if fx < 0:
            return straight_zero
        return r.straight(3 * street + (2 - t) + 1)

    def spot(self, bet: Bet) -> tuple[float, float]:
        """Where chips for ``bet`` are stacked on the layout."""
        kind = bet.kind
        nums = sorted(bet.numbers)
        ch = self.cell_h
        gl, top = self.grid_left, self.top
        if kind in (BetKind.COLUMN, BetKind.DOZEN) or not kind.inside:
            for b, rect in self.box_bets():
                if b == bet:
                    return rect.center
        if kind is BetKind.STRAIGHT:
            return self.cell_rect(nums[0]).center
        if kind is BetKind.SPLIT:
            a, b = nums
            if a == 0:
                return gl, self.cell_rect(b).centery
            ra, rb = self.cell_rect(a), self.cell_rect(b)
            return (ra.centerx + rb.centerx) / 2, (ra.centery + rb.centery) / 2
        if kind is BetKind.CORNER:
            ra, rb = self.cell_rect(nums[0]), self.cell_rect(nums[-1])
            return (ra.centerx + rb.centerx) / 2, (ra.centery + rb.centery) / 2
        if kind is BetKind.STREET:
            return self.cell_rect(nums[0]).centerx, top + 3 * ch
        if kind is BetKind.SIX_LINE:
            return self.cell_rect(nums[0]).right, top + 3 * ch
        if kind is BetKind.TRIO:
            return gl, top + (ch if 3 in bet.numbers else 2 * ch)
        if kind is BetKind.FIRST_FOUR:
            return gl, top + 3 * ch
        raise ValueError(f"no spot for {bet}")  # pragma: no cover


straight_zero = r.straight(0)
