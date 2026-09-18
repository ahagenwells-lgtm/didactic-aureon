import json
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LedgerEntry, Role, Tier, User, WalletBalance

USDT = "USDT"
ZERO = Decimal("0")
AMOUNT_QUANTUM = Decimal("0.000000000000000001")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_amount(value: Decimal) -> Decimal:
    return value.quantize(AMOUNT_QUANTUM, rounding=ROUND_DOWN)


def calculate_roi(principal: Decimal, annual_rate: Decimal, term_days: int) -> Decimal:
    return normalize_amount(principal * annual_rate * Decimal(term_days) / Decimal(365))


def new_referral_code(db: Session) -> str:
    for _ in range(10):
        code = secrets.token_urlsafe(9).replace("-", "A").replace("_", "B")[:12].upper()
        if db.scalar(select(User.id).where(User.referral_code == code)) is None:
            return code
    raise RuntimeError("could not generate a unique referral code")


def get_balance_for_update(db: Session, user_id: str, asset: str) -> WalletBalance:
    balance = db.scalar(
        select(WalletBalance)
        .where(WalletBalance.user_id == user_id, WalletBalance.asset == asset)
        .with_for_update()
    )
    if balance is None:
        balance = WalletBalance(user_id=user_id, asset=asset, available=ZERO, locked=ZERO)
        db.add(balance)
        db.flush()
    return balance


def post_balance_change(
    db: Session,
    *,
    user_id: str,
    asset: str,
    available_delta: Decimal = ZERO,
    locked_delta: Decimal = ZERO,
    event_type: str,
    reference_type: str,
    reference_id: str,
    metadata: dict | None = None,
) -> WalletBalance:
    """Atomically mutate a balance and create immutable ledger records for each changed bucket."""
    available_delta = normalize_amount(available_delta)
    locked_delta = normalize_amount(locked_delta)
    if available_delta == ZERO and locked_delta == ZERO:
        raise ValueError("at least one balance delta is required")
    balance = get_balance_for_update(db, user_id, asset)
    next_available = normalize_amount(balance.available + available_delta)
    next_locked = normalize_amount(balance.locked + locked_delta)
    if next_available < ZERO or next_locked < ZERO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient available balance")
    balance.available = next_available
    balance.locked = next_locked
    balance.version += 1
    metadata_json = json.dumps(metadata, sort_keys=True) if metadata else None
    if available_delta != ZERO:
        db.add(LedgerEntry(
            user_id=user_id, asset=asset, amount=available_delta, balance_kind="available",
            event_type=f"{event_type}_available", reference_type=reference_type,
            reference_id=reference_id, balance_after=next_available, metadata_json=metadata_json,
        ))
    if locked_delta != ZERO:
        db.add(LedgerEntry(
            user_id=user_id, asset=asset, amount=locked_delta, balance_kind="locked",
            event_type=f"{event_type}_locked", reference_type=reference_type,
            reference_id=reference_id, balance_after=next_locked, metadata_json=metadata_json,
        ))
    return balance


DEFAULT_TIERS = (
    ("BRONZE", "Bronze", "100", "999.999999999999999999", "0.05", "0.01"),
    ("GOLD", "Gold", "1000", "9999.999999999999999999", "0.085", "0.02"),
    ("VIP", "VIP", "10000", "1000000", "0.12", "0.03"),
)


def seed_defaults(db: Session) -> None:
    for code, name, minimum, maximum, roi, referral in DEFAULT_TIERS:
        if db.scalar(select(Tier).where(Tier.code == code)) is None:
            db.add(Tier(
                code=code, display_name=name, minimum=Decimal(minimum), maximum=Decimal(maximum),
                annual_roi_rate=Decimal(roi), referral_rate=Decimal(referral), is_active=True,
            ))
    db.commit()


def bootstrap_admin(db: Session, email: str | None, password: str | None, password_hasher) -> None:
    if not email or not password:
        return
    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing is None:
        db.add(User(
            email=email.lower(), password_hash=password_hasher(password), role=Role.ADMIN,
            referral_code=new_referral_code(db), is_active=True,
        ))
        db.commit()


def maturity_for(start: datetime, term_days: int) -> datetime:
    return start + timedelta(days=term_days)
