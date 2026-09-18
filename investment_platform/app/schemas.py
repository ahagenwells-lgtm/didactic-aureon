from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

SUPPORTED_ASSETS = {"BTC", "ETH", "USDT"}
Amount = Annotated[Decimal, Field(gt=0, max_digits=36, decimal_places=18)]
Rate = Annotated[Decimal, Field(ge=0, le=1, max_digits=20, decimal_places=18)]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


def normalized_asset(value: str) -> str:
    asset = value.upper()
    if asset not in SUPPORTED_ASSETS:
        raise ValueError(f"asset must be one of {', '.join(sorted(SUPPORTED_ASSETS))}")
    return asset


def reject_sensitive_material(value: str) -> str:
    lowered = value.lower()
    if any(marker in lowered for marker in ("private key", "seed phrase", "mnemonic", "xprv")):
        raise ValueError("never submit secret recovery material or private keys")
    if any(char.isspace() for char in value):
        raise ValueError("must not contain whitespace")
    return value


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    referral_code: str | None = Field(default=None, min_length=6, max_length=16, pattern=r"^[A-Za-z0-9]+$")


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(APIModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool
    referral_code: str
    referred_by_id: str | None
    created_at: datetime


class BalanceOut(APIModel):
    asset: str
    available: Decimal
    locked: Decimal
    updated_at: datetime


class TierOut(APIModel):
    code: str
    display_name: str
    minimum: Decimal
    maximum: Decimal
    annual_roi_rate: Decimal
    referral_rate: Decimal
    is_active: bool
    updated_at: datetime


class RoiRequest(APIModel):
    tier_code: str = Field(min_length=3, max_length=16)
    amount: Amount
    term_days: int = Field(ge=30, le=365)

    @field_validator("tier_code")
    @classmethod
    def normalize_tier(cls, value: str) -> str:
        return value.upper()


class RoiQuote(APIModel):
    tier_code: str
    principal: Decimal
    term_days: int
    annual_roi_rate: Decimal
    expected_roi: Decimal
    projected_total: Decimal
    disclaimer: str


class CreateInvestmentRequest(RoiRequest):
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class InvestmentOut(APIModel):
    id: str
    tier_code: str
    principal: Decimal
    annual_roi_rate: Decimal
    expected_roi: Decimal
    term_days: int
    starts_at: datetime
    matures_at: datetime
    settled_at: datetime | None
    status: str


class ReceivingWalletCreate(APIModel):
    asset: str
    network: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    address: str = Field(min_length=20, max_length=180)
    label: str | None = Field(default=None, max_length=100)

    @field_validator("asset")
    @classmethod
    def valid_asset(cls, value: str) -> str:
        return normalized_asset(value)

    @field_validator("network")
    @classmethod
    def valid_network(cls, value: str) -> str:
        return value.upper()

    @field_validator("address")
    @classmethod
    def safe_address(cls, value: str) -> str:
        return reject_sensitive_material(value)


class ReceivingWalletOut(APIModel):
    id: str
    asset: str
    network: str
    address: str
    label: str | None
    is_active: bool


class DepositRequest(APIModel):
    receiving_wallet_id: str
    tx_hash: str = Field(min_length=20, max_length=255)
    amount: Amount

    @field_validator("tx_hash")
    @classmethod
    def safe_hash(cls, value: str) -> str:
        return reject_sensitive_material(value)


class DepositOut(APIModel):
    id: str
    receiving_wallet_id: str
    asset: str
    network: str
    tx_hash: str
    amount: Decimal
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    price_usd: Decimal | None


class WithdrawalRequest(APIModel):
    asset: str
    network: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    destination_address: str = Field(min_length=20, max_length=180)
    amount: Amount
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")

    @field_validator("asset")
    @classmethod
    def valid_asset(cls, value: str) -> str:
        return normalized_asset(value)

    @field_validator("network")
    @classmethod
    def valid_network(cls, value: str) -> str:
        return value.upper()

    @field_validator("destination_address")
    @classmethod
    def safe_destination(cls, value: str) -> str:
        return reject_sensitive_material(value)


class WithdrawalOut(APIModel):
    id: str
    asset: str
    network: str
    destination_address: str
    amount: Decimal
    status: str
    requested_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    external_tx_hash: str | None
    price_usd: Decimal | None


class ReviewRequest(APIModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)
    external_tx_hash: str | None = Field(default=None, min_length=20, max_length=255)

    @field_validator("external_tx_hash")
    @classmethod
    def safe_hash(cls, value: str | None) -> str | None:
        return reject_sensitive_material(value) if value else value


class TierUpdate(APIModel):
    minimum: Amount | None = None
    maximum: Amount | None = None
    annual_roi_rate: Rate | None = None
    referral_rate: Rate | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "TierUpdate":
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("maximum must be at least minimum")
        return self


class PriceOut(APIModel):
    asset: str
    usd_price: Decimal
    source: str
    updated_at: datetime
