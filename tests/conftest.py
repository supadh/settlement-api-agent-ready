from collections.abc import Generator

import pytest

import reconcile


@pytest.fixture(autouse=True)
def isolate_in_memory_ledger() -> Generator[None, None, None]:
    reconcile.charges.clear()
    reconcile.refunds.clear()
    reconcile.settlement_lines.clear()
    yield
    reconcile.charges.clear()
    reconcile.refunds.clear()
    reconcile.settlement_lines.clear()
