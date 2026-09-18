import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


MONEY = Numeric(36, 18)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class InvestmentStatus(str, enum.Enum):
    ACTIVE = "active"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    referred_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    referred_by: Mapped["User | None"] = relationship("User", remote_side=[id], foreign_keys=[referred_by_id])
    balances: Mapped[list["WalletBalance"]] = relationship(back_populates="user")


class WalletBalance(Base):
    __tablename__ = "wallet_balances"
    __table_args__ = (
        UniqueConstraint("user_id", "asset", name="uq_wallet_balance_user_asset"),
        CheckConstraint("available >= 0", name="ck_wallet_available_nonnegative"),
        CheckConstraint("locked >= 0", name="ck_wallet_locked_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(12), nullable=False)
    available: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    locked: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="balances")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("event_type", "reference_id", "asset", "user_id", name="uq_ledger_event_ref_asset_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    balance_kind: Mapped[str] = mapped_column(String(12), nullable=False)  # available or locked
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(48), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(80), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tier(Base):
    __tablename__ = "tiers"
    __table_args__ = (
        CheckConstraint("minimum > 0", name="ck_tier_minimum_positive"),
        CheckConstraint("maximum >= minimum", name="ck_tier_range"),
        CheckConstraint("annual_roi_rate >= 0", name="ck_tier_roi_positive"),
        CheckConstraint("referral_rate >= 0", name="ck_tier_referral_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(32), nullable=False)
    minimum: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    maximum: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_roi_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # 0.05 = 5%
    referral_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Investment(Base):
    __tablename__ = "investments"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_investment_user_idempotency"),
        CheckConstraint("principal > 0", name="ck_investment_principal_positive"),
        CheckConstraint("term_days >= 30 AND term_days <= 365", name="ck_investment_term_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tier_code: Mapped[str] = mapped_column(String(16), nullable=False)
    principal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_roi_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expected_roi: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    matures_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InvestmentStatus] = mapped_column(Enum(InvestmentStatus), default=InvestmentStatus.ACTIVE, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)


class ReceivingWallet(Base):
    __tablename__ = "receiving_wallets"
    __table_args__ = (UniqueConstraint("asset", "network", "address", name="uq_receiving_wallet"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset: Mapped[str] = mapped_column(String(12), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str] = mapped_column(String(180), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (
        UniqueConstraint("network", "tx_hash", name="uq_deposit_network_tx_hash"),
        CheckConstraint("amount > 0", name="ck_deposit_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    receiving_wallet_id: Mapped[str] = mapped_column(ForeignKey("receiving_wallets.id"), nullable=False)
    asset: Mapped[str] = mapped_column(String(12), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    tx_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_usd: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_withdrawal_user_idempotency"),
        UniqueConstraint("network", "external_tx_hash", name="uq_withdrawal_network_tx_hash"),
        CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(12), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(180), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_usd: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)


class PriceQuote(Base):
    __tablename__ = "price_quotes"

    asset: Mapped[str] = mapped_column(String(12), primary_key=True)
    usd_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
