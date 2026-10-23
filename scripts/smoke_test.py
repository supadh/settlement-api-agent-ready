import argparse
import time

import httpx

MERCHANT_ID = "qa-merchant"
CHARGE_AMOUNT_CENTS = 1250
PARTIAL_REFUND_CENTS = 250


def wait_until_ready(client: httpx.Client) -> None:
    for _ in range(20):
        try:
            response = client.get("/openapi.json")
            if response.status_code == 200:
                return
        except httpx.ConnectError:
            pass
        time.sleep(0.25)
    raise RuntimeError("API did not become ready within five seconds")


def post_settlement_line(
    client: httpx.Client, processor_ref: str, charge_id: str, amount_cents: int
) -> None:
    response = client.post(
        "/settlement-lines",
        json={
            "processor_ref": processor_ref,
            "charge_id": charge_id,
            "amount_cents": amount_cents,
        },
    )
    response.raise_for_status()


def assert_single_match(client: httpx.Client, expected_ledger_cents: int) -> None:
    reconciliation_response = client.get(f"/merchants/{MERCHANT_ID}/reconciliation")
    reconciliation_response.raise_for_status()
    reconciliation = reconciliation_response.json()
    if len(reconciliation["matched"]) != 1:
        raise RuntimeError("Expected one matched charge in reconciliation response")
    if reconciliation["mismatched"]:
        raise RuntimeError("Expected no reconciliation mismatches")
    if reconciliation["matched"][0]["ledger_amount_cents"] != expected_ledger_cents:
        raise RuntimeError("Matched ledger amount does not reflect refunds")


def run_smoke_test(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        wait_until_ready(client)

        charge_response = client.post(
            "/charges",
            json={
                "merchant_id": MERCHANT_ID,
                "amount_cents": CHARGE_AMOUNT_CENTS,
                "card_token": "qa-token-not-a-real-card",
            },
        )
        charge_response.raise_for_status()
        charge_id = charge_response.json()["id"]

        post_settlement_line(
            client, "qa-processor-reference", charge_id, CHARGE_AMOUNT_CENTS
        )
        assert_single_match(client, CHARGE_AMOUNT_CENTS)

        refund_response = client.post(
            f"/charges/{charge_id}/refunds",
            json={"amount_cents": PARTIAL_REFUND_CENTS, "reason": "qa partial refund"},
        )
        refund_response.raise_for_status()
        post_settlement_line(
            client, "qa-processor-adjustment", charge_id, -PARTIAL_REFUND_CENTS
        )
        assert_single_match(client, CHARGE_AMOUNT_CENTS - PARTIAL_REFUND_CENTS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running Settlement API",
    )
    arguments = parser.parse_args()
    run_smoke_test(arguments.base_url)
    print("Interactive API smoke test passed")


if __name__ == "__main__":
    main()
