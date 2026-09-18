# Investment platform backend (simulation only)

This FastAPI service models an investment platform with tiered ROI projections, a referral programme, manually reviewed crypto deposits and withdrawals, an append-only wallet ledger, live price snapshots, and admin controls.

It is intentionally a **simulation and accounting workflow**, not a live-custody system: it does not hold private keys, sign blockchain transactions, initiate transfers, or promise investment returns. Production deployment requires legal/compliance review, KYC/AML/sanctions controls, audited custody infrastructure, a transaction-monitoring provider, rate limiting at the edge, encrypted backups, and a managed database.

## Run locally

```powershell
cd investment_platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set a unique APP_SECRET_KEY and bootstrap credentials in .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the responsive web application and `http://127.0.0.1:8000/docs` for the API reference. The bootstrap admin is only created when both `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are configured.

Run the critical workflow test with `pytest -q` from this directory. For container use, build `Dockerfile` only after supplying production environment variables through your deployment secret manager; do not bake `.env` into the image.

## Web application

The site at `/` is a responsive single-page dashboard served by FastAPI itself. It uses same-origin API requests and keeps the bearer token only in browser session storage. It provides:

- public tier cards, ROI projections, and cached market snapshots;
- sign-in and registration, including optional referral codes;
- balance, position, deposit, withdrawal, and ledger views;
- manual deposit/withdrawal submission flows; and
- an administrator-only review workspace for pending transfers, public receiving addresses, live-price refreshes, and future tier/referral-rate changes.

The web client never requests or stores wallet private keys, recovery phrases, or seed material.

## Key workflows

1. Register and authenticate to obtain a short-lived bearer token.
2. An administrator registers receiving wallet addresses for supported assets.
3. A user submits a deposit with an on-chain transaction hash; an administrator verifies it externally and approves or rejects it. Approval credits the internal available balance exactly once.
4. A user may create an investment only from their available USDT balance. The service locks the principal, calculates an expected simple ROI from the chosen tier and term, and awards a configured referral bonus to their referrer.
5. A user requests a withdrawal. It stays pending until an administrator independently performs/verifies the transfer and records an external transaction hash. Approval debits the internal available balance exactly once.

Prices are fetched from CoinGecko's public simple-price endpoint and cached; a conservative configured fallback is used if the endpoint is unavailable. This price feed is informational and **not** a trade-execution oracle.

## Security properties

- Argon2 password hashing; passwords are never returned or logged.
- Signed JWTs with issuer/audience checks and 30-minute default lifetime.
- Role-gated admin endpoints and disabled user self-assignment of roles.
- Decimal monetary values, database transactions, check constraints, row versioning, unique transaction hashes, and unique idempotency keys.
- Public address validation and transaction hashes are stored, but private keys/seeds are never accepted.
- CORS is deny-by-default, debug errors are disabled, and security headers are set on each response.

Use HTTPS behind a reverse proxy, set `APP_SECRET_KEY` from a secret manager, use PostgreSQL (not SQLite) for multi-worker production, and configure `CORS_ORIGINS` to the exact frontend domains before exposing this service.
