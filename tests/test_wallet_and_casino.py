from __future__ import annotations

import pytest

from neon_royale.core.casino import COMP_THRESHOLD, Casino
from neon_royale.core.money import dollars
from neon_royale.core.save import COMP_AMOUNT, STARTING_BANKROLL, Profile
from neon_royale.core.wallet import InsufficientFundsError, Wallet


def test_wallet_debit_and_credit() -> None:
    wallet = Wallet(dollars(100))
    wallet.debit(dollars(30))
    wallet.credit(dollars(45))
    assert wallet.balance == dollars(115)


def test_wallet_refuses_overdraft() -> None:
    wallet = Wallet(dollars(10))
    with pytest.raises(InsufficientFundsError) as info:
        wallet.debit(dollars(10.01))
    assert info.value.needed == 1001 and info.value.available == 1000
    assert wallet.balance == dollars(10)


@pytest.mark.parametrize("method", ["debit", "credit"])
def test_wallet_rejects_negative_amounts(method: str) -> None:
    with pytest.raises(ValueError):
        getattr(Wallet(100), method)(-1)


def test_wallet_can_afford() -> None:
    wallet = Wallet(500)
    assert wallet.can_afford(500)
    assert not wallet.can_afford(501)
    assert not wallet.can_afford(-1)


def test_new_casino_uses_starting_bankroll() -> None:
    assert Casino().balance == STARTING_BANKROLL


def test_comp_only_when_broke() -> None:
    casino = Casino(Profile(balance=COMP_THRESHOLD))
    assert not casino.comp_available
    assert casino.claim_comp() == 0

    casino = Casino(Profile(balance=COMP_THRESHOLD - 1))
    assert casino.comp_available
    assert casino.claim_comp() == COMP_AMOUNT
    assert casino.balance == COMP_THRESHOLD - 1 + COMP_AMOUNT
    assert casino.profile.comps_received == 1
    assert not casino.comp_available


def test_sync_copies_balance_into_profile() -> None:
    casino = Casino(Profile(balance=dollars(50)))
    casino.wallet.debit(dollars(20))
    assert casino.sync().balance == dollars(30)


def test_record_round_tracks_stats() -> None:
    casino = Casino()
    casino.record_round("blackjack", wagered=dollars(10), returned=dollars(25))
    casino.record_round("blackjack", wagered=dollars(10), returned=0)
    stats = casino.profile.stats["blackjack"]
    assert stats.rounds == 2
    assert stats.net == dollars(5)
    assert stats.biggest_win == dollars(15)
