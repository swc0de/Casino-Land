"""Game rules and state. Pure Python: nothing here may import pygame or the UI.

Keeping the rules free of presentation means every payout and edge case can be
tested without opening a window. ``tests/test_architecture.py`` enforces this.
"""
