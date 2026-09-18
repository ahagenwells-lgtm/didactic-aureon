import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .models import (
    Deposit,
    Investment,
    InvestmentStatus,
    LedgerEntry,
    PriceQuote,
    ReceivingWallet,
    ReviewStatus,
    Role,
    Tier,
    User,
    WalletBalance,
    Withdrawal,
)
from .pricing import ensure_price_quotes, refresh_prices
from .schemas import (
    BalanceOut,
    CreateInvestmentRequest,
    DepositOut,
    DepositRequest,
    LoginRequest,
    PriceOut,
    ReceivingWalletCreate,
    ReceivingWalletOut,
    RegisterRequest,
    ReviewRequest,
    RoiQuote,
    RoiRequest,
    TierOut,
    TierUpdate,
    TokenResponse,
    UserOut,
    WithdrawalOut,
    WithdrawalRequest,
)
from .security import create_access_token, get_current_user, hash_password, require_admin, settings, verify_password
from .services import (
    USDT,
    bootstrap_admin,
    calculate_roi,
    maturity_for,
    new_referral_code,
    normalize_amount,
    post_balance_change,
    seed_defaults,
    utcnow,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_defaults(db)
        ensure_price_quotes(db)
        bootstrap_password = settings.bootstrap_admin_password.get_secret_value() if settings.bootstrap_admin_password else None
        bootstrap_admin(db, settings.bootstrap_admin_email, bootstrap_password, hash_password)
    stop_price_refresh = asyncio.Event()

    async def price_refresh_loop() -> None:
        # Each process owns a cache refresh loop. For multi-worker production, move this to one scheduled worker.
        while not stop_price_refresh.is_set():
            try:
                with SessionLocal() as price_db:
                    await refresh_prices(price_db)
            except Exception:
                # The fallback quote remains available; don't take down the API because a public feed is unavailable.
                pass
            try:
                await asyncio.wait_for(stop_price_refresh.wait(), timeout=settings.price_cache_seconds)
            except TimeoutError:
                continue

    refresh_task = asyncio.create_task(price_refresh_loop())
    try:
        yield
    finally:
        stop_price_refresh.set()
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task


app = FastAPI(
    title="Investment Platform API",
    version="1.0.0",
    description="Simulated investment accounting and manually verified crypto transfer workflow. Not a custody service.",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith(("/auth", "/me", "/wallet", "/admin")) else "private, max-age=30"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, __: IntegrityError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "conflicting or duplicate request"})


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def get_active_tier(db: Session, code: str) -> Tier:
    tier = db.scalar(select(Tier).where(Tier.code == code, Tier.is_active.is_(True)))
    if tier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active tier not found")
    return tier


def tier_quote(tier: Tier, principal: Decimal, term_days: int) -> RoiQuote:
    if principal < tier.minimum or principal > tier.maximum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"amount must be between {tier.minimum} and {tier.maximum} USDT for {tier.code}",
        )
    expected_roi = calculate_roi(principal, tier.annual_roi_rate, term_days)
    return RoiQuote(
        tier_code=tier.code, principal=principal, term_days=term_days, annual_roi_rate=tier.annual_roi_rate,
        expected_roi=expected_roi, projected_total=normalize_amount(principal + expected_roi),
        disclaimer="Projection only; no return is guaranteed. This simulation does not constitute investment advice.",
    )


def current_price(db: Session, asset: str) -> Decimal | None:
    quote = db.get(PriceQuote, asset)
    return quote.usd_price if quote else None


def owned_or_404(db: Session, model, object_id: str, user_id: str):
    obj = db.get(model, object_id)
    if obj is None or obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return obj


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "investment-platform-api"}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise conflict("an account already exists for that email")
    referrer: User | None = None
    if payload.referral_code:
        referrer = db.scalar(select(User).where(User.referral_code == payload.referral_code.upper(), User.is_active.is_(True)))
        if referrer is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid referral code")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role=Role.USER,
        referral_code=new_referral_code(db),
        referred_by_id=referrer.id if referrer else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    return TokenResponse(access_token=create_access_token(user), expires_in=settings.access_token_expire_minutes * 60)


@app.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/wallet/balances", response_model=list[BalanceOut])
def balances(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WalletBalance]:
    return list(db.scalars(select(WalletBalance).where(WalletBalance.user_id == current_user.id).order_by(WalletBalance.asset)))


@app.get("/wallet/ledger")
def ledger(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    safe_limit = min(max(limit, 1), 200)
    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.user_id == current_user.id).order_by(LedgerEntry.created_at.desc()).limit(safe_limit)
    )
    return [
        {
            "id": entry.id, "asset": entry.asset, "amount": str(entry.amount), "balance_kind": entry.balance_kind,
            "event_type": entry.event_type, "reference_type": entry.reference_type,
            "reference_id": entry.reference_id, "balance_after": str(entry.balance_after), "created_at": entry.created_at,
        }
        for entry in entries
    ]


@app.get("/tiers", response_model=list[TierOut])
def tiers(db: Session = Depends(get_db)) -> list[Tier]:
    return list(db.scalars(select(Tier).where(Tier.is_active.is_(True)).order_by(Tier.minimum)))


@app.post("/roi/quote", response_model=RoiQuote)
def roi_quote(payload: RoiRequest, db: Session = Depends(get_db)) -> RoiQuote:
    return tier_quote(get_active_tier(db, payload.tier_code), normalize_amount(payload.amount), payload.term_days)


@app.post("/investments", response_model=InvestmentOut, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: CreateInvestmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Investment:
    existing = db.scalar(select(Investment).where(Investment.user_id == current_user.id, Investment.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return existing
    principal = normalize_amount(payload.amount)
    tier = get_active_tier(db, payload.tier_code)
    quote = tier_quote(tier, principal, payload.term_days)
    now = utcnow()
    investment = Investment(
        user_id=current_user.id, tier_code=tier.code, principal=principal, annual_roi_rate=tier.annual_roi_rate,
        expected_roi=quote.expected_roi, term_days=payload.term_days, starts_at=now,
        matures_at=maturity_for(now, payload.term_days), status=InvestmentStatus.ACTIVE,
        idempotency_key=payload.idempotency_key,
    )
    db.add(investment)
    db.flush()
    post_balance_change(
        db, user_id=current_user.id, asset=USDT, available_delta=-principal, locked_delta=principal,
        event_type="investment_principal", reference_type="investment", reference_id=investment.id,
        metadata={"tier": tier.code, "term_days": payload.term_days},
    )
    if current_user.referred_by_id:
        referral_bonus = normalize_amount(principal * tier.referral_rate)
        if referral_bonus > 0:
            post_balance_change(
                db, user_id=current_user.referred_by_id, asset=USDT, available_delta=referral_bonus,
                event_type="referral_bonus", reference_type="investment", reference_id=investment.id,
                metadata={"referred_user_id": current_user.id, "tier": tier.code, "rate": str(tier.referral_rate)},
            )
    db.commit()
    db.refresh(investment)
    return investment


@app.get("/investments", response_model=list[InvestmentOut])
def investments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Investment]:
    return list(db.scalars(select(Investment).where(Investment.user_id == current_user.id).order_by(Investment.starts_at.desc())))


@app.post("/investments/{investment_id}/settle", response_model=InvestmentOut)
def settle_investment(
    investment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Investment:
    investment = owned_or_404(db, Investment, investment_id, current_user.id)
    if investment.status != InvestmentStatus.ACTIVE:
        raise conflict("investment is not active")
    matures_at = investment.matures_at
    if matures_at.tzinfo is None:  # SQLite does not preserve timezone info.
        matures_at = matures_at.replace(tzinfo=timezone.utc)
    if utcnow() < matures_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="investment has not matured")
    payout = normalize_amount(investment.principal + investment.expected_roi)
    post_balance_change(
        db, user_id=current_user.id, asset=USDT, available_delta=payout, locked_delta=-investment.principal,
        event_type="investment_settlement", reference_type="investment", reference_id=investment.id,
        metadata={"principal": str(investment.principal), "roi": str(investment.expected_roi)},
    )
    investment.status = InvestmentStatus.SETTLED
    investment.settled_at = utcnow()
    db.commit()
    return investment


@app.get("/wallet/receiving-addresses", response_model=list[ReceivingWalletOut])
def receiving_addresses(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ReceivingWallet]:
    return list(db.scalars(select(ReceivingWallet).where(ReceivingWallet.is_active.is_(True)).order_by(ReceivingWallet.asset, ReceivingWallet.network)))


@app.post("/deposits", response_model=DepositOut, status_code=status.HTTP_201_CREATED)
def submit_deposit(
    payload: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deposit:
    wallet = db.get(ReceivingWallet, payload.receiving_wallet_id)
    if wallet is None or not wallet.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="receiving wallet not found or inactive")
    if db.scalar(select(Deposit.id).where(Deposit.network == wallet.network, Deposit.tx_hash == payload.tx_hash)):
        raise conflict("this transaction hash has already been submitted")
    deposit = Deposit(
        user_id=current_user.id, receiving_wallet_id=wallet.id, asset=wallet.asset, network=wallet.network,
        tx_hash=payload.tx_hash, amount=normalize_amount(payload.amount), status=ReviewStatus.PENDING,
        price_usd=current_price(db, wallet.asset),
    )
    db.add(deposit)
    db.commit()
    db.refresh(deposit)
    return deposit


@app.get("/deposits", response_model=list[DepositOut])
def deposits(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Deposit]:
    return list(db.scalars(select(Deposit).where(Deposit.user_id == current_user.id).order_by(Deposit.submitted_at.desc())))


@app.post("/withdrawals", response_model=WithdrawalOut, status_code=status.HTTP_201_CREATED)
def request_withdrawal(
    payload: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Withdrawal:
    existing = db.scalar(select(Withdrawal).where(Withdrawal.user_id == current_user.id, Withdrawal.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return existing
    amount = normalize_amount(payload.amount)
    withdrawal = Withdrawal(
        user_id=current_user.id, asset=payload.asset, network=payload.network, destination_address=payload.destination_address,
        amount=amount, status=ReviewStatus.PENDING, idempotency_key=payload.idempotency_key,
        price_usd=current_price(db, payload.asset),
    )
    db.add(withdrawal)
    db.flush()
    post_balance_change(
        db, user_id=current_user.id, asset=payload.asset, available_delta=-amount, locked_delta=amount,
        event_type="withdrawal_reservation", reference_type="withdrawal", reference_id=withdrawal.id,
        metadata={"network": payload.network, "destination": payload.destination_address},
    )
    db.commit()
    db.refresh(withdrawal)
    return withdrawal


@app.get("/withdrawals", response_model=list[WithdrawalOut])
def withdrawals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Withdrawal]:
    return list(db.scalars(select(Withdrawal).where(Withdrawal.user_id == current_user.id).order_by(Withdrawal.requested_at.desc())))


@app.get("/prices", response_model=list[PriceOut])
def prices(db: Session = Depends(get_db)) -> list[PriceQuote]:
    return list(db.scalars(select(PriceQuote).order_by(PriceQuote.asset)))


@app.post("/admin/prices/refresh", response_model=list[PriceOut])
async def admin_refresh_prices(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[PriceQuote]:
    return await refresh_prices(db)


@app.get("/admin/users", response_model=list[UserOut])
def admin_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc()).limit(500)))


@app.post("/admin/receiving-wallets", response_model=ReceivingWalletOut, status_code=status.HTTP_201_CREATED)
def admin_create_receiving_wallet(
    payload: ReceivingWalletCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReceivingWallet:
    if db.scalar(select(ReceivingWallet.id).where(
        ReceivingWallet.asset == payload.asset, ReceivingWallet.network == payload.network, ReceivingWallet.address == payload.address,
    )):
        raise conflict("receiving wallet already exists")
    wallet = ReceivingWallet(**payload.model_dump())
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@app.post("/admin/receiving-wallets/{wallet_id}/disable", response_model=ReceivingWalletOut)
def admin_disable_receiving_wallet(
    wallet_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReceivingWallet:
    wallet = db.get(ReceivingWallet, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="receiving wallet not found")
    wallet.is_active = False
    db.commit()
    return wallet


@app.get("/admin/deposits", response_model=list[DepositOut])
def admin_deposits(
    review_status: ReviewStatus | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Deposit]:
    statement = select(Deposit).order_by(Deposit.submitted_at.desc()).limit(500)
    if review_status:
        statement = statement.where(Deposit.status == review_status)
    return list(db.scalars(statement))


@app.post("/admin/deposits/{deposit_id}/review", response_model=DepositOut)
def admin_review_deposit(
    deposit_id: str,
    payload: ReviewRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Deposit:
    deposit = db.scalar(select(Deposit).where(Deposit.id == deposit_id).with_for_update())
    if deposit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deposit not found")
    if deposit.status != ReviewStatus.PENDING:
        raise conflict("deposit was already reviewed")
    deposit.status = ReviewStatus.APPROVED if payload.approve else ReviewStatus.REJECTED
    deposit.reviewed_by_id = admin.id
    deposit.reviewed_at = utcnow()
    deposit.review_note = payload.note
    if payload.approve:
        post_balance_change(
            db, user_id=deposit.user_id, asset=deposit.asset, available_delta=deposit.amount,
            event_type="deposit_approved", reference_type="deposit", reference_id=deposit.id,
            metadata={"network": deposit.network, "tx_hash": deposit.tx_hash, "reviewed_by": admin.id},
        )
    db.commit()
    return deposit


@app.get("/admin/withdrawals", response_model=list[WithdrawalOut])
def admin_withdrawals(
    review_status: ReviewStatus | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Withdrawal]:
    statement = select(Withdrawal).order_by(Withdrawal.requested_at.desc()).limit(500)
    if review_status:
        statement = statement.where(Withdrawal.status == review_status)
    return list(db.scalars(statement))


@app.post("/admin/withdrawals/{withdrawal_id}/review", response_model=WithdrawalOut)
def admin_review_withdrawal(
    withdrawal_id: str,
    payload: ReviewRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Withdrawal:
    withdrawal = db.scalar(select(Withdrawal).where(Withdrawal.id == withdrawal_id).with_for_update())
    if withdrawal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="withdrawal not found")
    if withdrawal.status != ReviewStatus.PENDING:
        raise conflict("withdrawal was already reviewed")
    if payload.approve and not payload.external_tx_hash:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="external transaction hash is required for approval")
    if payload.approve and db.scalar(select(Withdrawal.id).where(
        Withdrawal.network == withdrawal.network, Withdrawal.external_tx_hash == payload.external_tx_hash,
    )):
        raise conflict("external transaction hash has already been recorded")
    withdrawal.status = ReviewStatus.APPROVED if payload.approve else ReviewStatus.REJECTED
    withdrawal.reviewed_by_id = admin.id
    withdrawal.reviewed_at = utcnow()
    withdrawal.review_note = payload.note
    withdrawal.external_tx_hash = payload.external_tx_hash if payload.approve else None
    if payload.approve:
        post_balance_change(
            db, user_id=withdrawal.user_id, asset=withdrawal.asset, locked_delta=-withdrawal.amount,
            event_type="withdrawal_sent", reference_type="withdrawal", reference_id=withdrawal.id,
            metadata={"network": withdrawal.network, "external_tx_hash": payload.external_tx_hash, "reviewed_by": admin.id},
        )
    else:
        post_balance_change(
            db, user_id=withdrawal.user_id, asset=withdrawal.asset,
            available_delta=withdrawal.amount, locked_delta=-withdrawal.amount,
            event_type="withdrawal_released", reference_type="withdrawal", reference_id=withdrawal.id,
            metadata={"reviewed_by": admin.id, "reason": payload.note or "rejected"},
        )
    db.commit()
    return withdrawal


@app.patch("/admin/tiers/{tier_code}", response_model=TierOut)
def admin_update_tier(
    tier_code: str,
    payload: TierUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Tier:
    tier = db.scalar(select(Tier).where(Tier.code == tier_code.upper()).with_for_update())
    if tier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tier not found")
    changes = payload.model_dump(exclude_unset=True)
    for name, value in changes.items():
        setattr(tier, name, normalize_amount(value) if name in {"minimum", "maximum", "annual_roi_rate", "referral_rate"} else value)
    if tier.maximum < tier.minimum:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="maximum must be at least minimum")
    db.commit()
    return tier


@app.get("/admin/dashboard")
def admin_dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "active_investments": db.scalar(select(func.count()).select_from(Investment).where(Investment.status == InvestmentStatus.ACTIVE)),
        "pending_deposits": db.scalar(select(func.count()).select_from(Deposit).where(Deposit.status == ReviewStatus.PENDING)),
        "pending_withdrawals": db.scalar(select(func.count()).select_from(Withdrawal).where(Withdrawal.status == ReviewStatus.PENDING)),
        "wallet_available_by_asset": [
            {"asset": asset, "available": str(total or 0)}
            for asset, total in db.execute(select(WalletBalance.asset, func.sum(WalletBalance.available)).group_by(WalletBalance.asset))
        ],
    }
