"""Critical accounting workflow smoke test.

Run from investment_platform/: pytest -q
"""
import os
from pathlib import Path

os.environ["APP_SECRET_KEY"] = "test-secret-key-that-is-long-enough-to-be-safe-in-tests-only"
os.environ["DATABASE_URL"] = "sqlite:///./test_investment_platform.db"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@test.example"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "bootstrap-admin-password"
os.environ["PRICE_CACHE_SECONDS"] = "300"

Path("test_investment_platform.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_manual_crypto_workflow_and_referral_credit() -> None:
    with TestClient(app) as client:
        admin_token = login(client, "admin@test.example", "bootstrap-admin-password")

        referrer = client.post("/auth/register", json={"email": "referrer@test.example", "password": "a-secure-password"})
        assert referrer.status_code == 201, referrer.text
        referrer_data = referrer.json()

        investor = client.post("/auth/register", json={
            "email": "investor@test.example", "password": "another-secure-password",
            "referral_code": referrer_data["referral_code"],
        })
        assert investor.status_code == 201, investor.text
        investor_token = login(client, "investor@test.example", "another-secure-password")

        receiving_wallet = client.post("/admin/receiving-wallets", headers=bearer(admin_token), json={
            "asset": "USDT", "network": "ETHEREUM", "address": "0x1234567890abcdef1234567890abcdef12345678", "label": "Treasury",
        })
        assert receiving_wallet.status_code == 201, receiving_wallet.text

        deposit = client.post("/deposits", headers=bearer(investor_token), json={
            "receiving_wallet_id": receiving_wallet.json()["id"],
            "tx_hash": "0x" + "a" * 64,
            "amount": "1500",
        })
        assert deposit.status_code == 201, deposit.text
        approved_deposit = client.post(
            f"/admin/deposits/{deposit.json()['id']}/review", headers=bearer(admin_token), json={"approve": True, "note": "confirmed on-chain"},
        )
        assert approved_deposit.status_code == 200, approved_deposit.text

        investment = client.post("/investments", headers=bearer(investor_token), json={
            "tier_code": "GOLD", "amount": "1000", "term_days": 30, "idempotency_key": "investment-request-0001",
        })
        assert investment.status_code == 201, investment.text
        assert investment.json()["tier_code"] == "GOLD"

        referrer_token = login(client, "referrer@test.example", "a-secure-password")
        referrer_balance = client.get("/wallet/balances", headers=bearer(referrer_token)).json()
        assert len(referrer_balance) == 1
        assert referrer_balance[0]["asset"] == "USDT"
        assert referrer_balance[0]["available"] == "20.000000000000000000"

        withdrawal = client.post("/withdrawals", headers=bearer(investor_token), json={
            "asset": "USDT", "network": "ETHEREUM", "destination_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "amount": "25", "idempotency_key": "withdrawal-request-0001",
        })
        assert withdrawal.status_code == 201, withdrawal.text
        approved_withdrawal = client.post(
            f"/admin/withdrawals/{withdrawal.json()['id']}/review", headers=bearer(admin_token),
            json={"approve": True, "external_tx_hash": "0x" + "b" * 64},
        )
        assert approved_withdrawal.status_code == 200, approved_withdrawal.text

        balances = client.get("/wallet/balances", headers=bearer(investor_token)).json()
        usdt = next(balance for balance in balances if balance["asset"] == "USDT")
        assert usdt["available"] == "475.000000000000000000"
        assert usdt["locked"] == "1000.000000000000000000"
