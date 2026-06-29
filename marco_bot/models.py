from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    is_group_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    ads_posted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safe_sells_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safe_sell_volume: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    post_ad_cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Ad(Base):
    __tablename__ = "ads"

    ad_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ref_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    funds_source: Mapped[str] = mapped_column(String(32), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(64), nullable=False)
    dm_username: Mapped[str] = mapped_column(String(255), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    channel_msg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_msg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    tx_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    coin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chain: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    payment_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deposit_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    withdrawal_destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GlobalStats(Base):
    __tablename__ = "global_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_safe_sold_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    today_safe_sold_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    today_reset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_deals_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class RateTier(Base):
    __tablename__ = "rate_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    min_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    max_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    rate_inr: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class RequiredGroup(Base):
    __tablename__ = "required_groups"

    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    invite_link: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)


class CaptchaAttempt(Base):
    __tablename__ = "captcha_attempts"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    captcha_code: Mapped[str] = mapped_column(String(8), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    stack_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class PaymentMode(Base):
    __tablename__ = "payment_modes"

    payment_mode: Mapped[str] = mapped_column(String(32), primary_key=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
