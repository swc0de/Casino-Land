"""The casino floor: the player's wallet tied to their saved profile."""

from __future__ import annotations

from .money import Cents, dollars
from .save import COMP_AMOUNT, GameStats, Profile
from .wallet import Wallet

# Below this the player cannot sit at any table, so the house offers a free top-up.
COMP_THRESHOLD: Cents = dollars(10)


class Casino:
    def __init__(self, profile: Profile | None = None) -> None:
        self.profile = profile or Profile()
        self.wallet = Wallet(self.profile.balance)

    @property
    def balance(self) -> Cents:
        return self.wallet.balance

    def sync(self) -> Profile:
        """Copy live state into the profile so it can be saved."""
        self.profile.balance = self.wallet.balance
        return self.profile

    @property
    def comp_available(self) -> bool:
        return self.wallet.balance < COMP_THRESHOLD

    def claim_comp(self) -> Cents:
        """Give a broke player a fresh stack of play chips. Returns the amount granted."""
        if not self.comp_available:
            return 0
        self.wallet.credit(COMP_AMOUNT)
        self.profile.comps_received += 1
        return COMP_AMOUNT

    def record_round(self, game: str, wagered: Cents, returned: Cents) -> None:
        self.profile.stats.setdefault(game, GameStats()).record(wagered, returned)
