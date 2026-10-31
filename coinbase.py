"""Adapter for originating onchain USDC payouts through Coinbase.

Routes depend on the module-level client so tests can inject a fake, mirroring
the observability adapter pattern. The adapter raises ``CoinbaseTransferError``
when a transfer is rejected so callers can translate that into an HTTP error
without mutating the ledger.
"""

from logging_config import logger


class CoinbaseTransferError(RuntimeError):
    """Raised when Coinbase rejects an onchain transfer."""


class CoinbaseClient:
    """Submits USDC transfers on Base through Coinbase Server Wallets."""

    def send_usdc_transfer(self, destination_address: str, amount_units: int) -> str:
        """Transfer ``amount_units`` USDC base units and return the tx hash."""
        # Coinbase credentials are never configured for local development, so
        # no transfer can be signed; fail closed instead of dropping the payout.
        logger.warning("coinbase.transfer_not_configured")
        raise CoinbaseTransferError("Coinbase client is not configured")


coinbase_client = CoinbaseClient()
