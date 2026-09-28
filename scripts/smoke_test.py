import argparse
import time

import httpx


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


def run_smoke_test(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        wait_until_ready(client)

        charge_response = client.post(
            "/charges",
            json={
                "merchant_id": "qa-merchant",
                "amount_cents": 1250,
                "card_token": "qa-token-not-a-real-card",
            },
        )
        charge_response.raise_for_status()
        charge_id = charge_response.json()["id"]

        settlement_response = client.post(
            "/settlement-lines",
            json={
                "processor_ref": "qa-processor-reference",
                "charge_id": charge_id,
                "amount_cents": 1250,
            },
        )
        settlement_response.raise_for_status()

        reconciliation_response = client.get("/merchants/qa-merchant/reconciliation")
        reconciliation_response.raise_for_status()
        reconciliation = reconciliation_response.json()
        if len(reconciliation["matched"]) != 1:
            raise RuntimeError("Expected one matched charge in reconciliation response")
        if reconciliation["mismatched"]:
            raise RuntimeError("Expected no reconciliation mismatches")


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
