from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import AsyncIterator

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings
from .constants import DEFAULT_RATE_TIERS, EXPRESS_PAYMENT_MODES
from .models import Base, GlobalStats, PaymentMode, RateTier, RequiredGroup

SessionFactory: async_sessionmaker[AsyncSession] | None = None
Engine: AsyncEngine | None = None


def configure_database(database_url: str) -> None:
    global Engine, SessionFactory
    engine = create_async_engine(database_url, future=True)
    Engine = engine
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if SessionFactory is None:
        raise RuntimeError("Database is not configured. Call configure_database() first.")
    return SessionFactory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(settings: Settings) -> None:
    if Engine is None:
        raise RuntimeError("Database is not configured. Call configure_database() first.")
    async with Engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_scope() as session:
        stats = await session.get(GlobalStats, 1)
        if not stats:
            session.add(GlobalStats(id=1))

        for mode in EXPRESS_PAYMENT_MODES:
            existing_mode = await session.get(PaymentMode, mode)
            if not existing_mode:
                session.add(PaymentMode(payment_mode=mode, available=True))

        result = await session.execute(select(RateTier.id).limit(1))
        if result.scalar_one_or_none() is None:
            for mode, tiers in DEFAULT_RATE_TIERS.items():
                for min_usd, max_usd, rate in tiers:
                    session.add(
                        RateTier(
                            payment_mode=mode,
                            min_usd=Decimal(str(min_usd)),
                            max_usd=Decimal(str(max_usd)) if max_usd is not None else None,
                            rate_inr=Decimal(str(rate)),
                        )
                    )

        if settings.required_groups:
            await session.execute(delete(RequiredGroup))
            for group in settings.required_groups:
                session.add(
                    RequiredGroup(
                        group_id=group.group_id,
                        invite_link=group.invite_link,
                        label=group.label,
                    )
                )
