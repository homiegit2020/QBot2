from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared, but keep startup graceful.
    load_dotenv = None


@dataclass(frozen=True)
class ConfiguredGroup:
    group_id: str
    invite_link: str
    label: str


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: list[int]
    admin_review_chat_id: str | None
    ads_channel_id: str | None
    ads_group_id: str | None
    required_groups: list[ConfiguredGroup]
    post_ad_cooldown_seconds: int
    timezone: str
    support_url: str
    banner_image_path: Path | None
    deposit_addresses: dict[str, dict[str, str]]
    trx_address: str | None
    bnb_address: str | None
    eth_address: str | None
    etherscan_api_key: str | None
    infura_url: str | None
    infura_api_key: str | None
    trongrid_api_key: str | None
    telegram_api_id: str | None
    telegram_api_hash: str | None
    telegram_phone: str | None


def _split_ints(value: str | None) -> list[int]:
    if not value:
        return []
    ids: list[int] = []
    for piece in value.split(","):
        piece = piece.strip()
        if piece:
            ids.append(int(piece))
    return ids


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    return json.loads(raw)


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _required_groups_from_env() -> list[ConfiguredGroup]:
    groups: list[ConfiguredGroup] = []
    for idx in (1, 2):
        group_id = os.getenv(f"REQUIRED_GROUP_{idx}_ID", "").strip()
        link = os.getenv(f"REQUIRED_GROUP_{idx}_LINK", "").strip()
        if group_id and link:
            groups.append(ConfiguredGroup(group_id=group_id, invite_link=link, label=f"Join Group {idx}"))
    return groups


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + database_url.removeprefix("sqlite:///")
    return database_url


def _deposit_addresses_from_env() -> dict[str, dict[str, str]]:
    addresses = _json_env("DEPOSIT_ADDRESSES_JSON", {})
    if not isinstance(addresses, dict):
        addresses = {}

    trx_address = _optional_env("TRX_ADDRESS")
    bnb_address = _optional_env("BNB_ADDRESS")
    eth_address = _optional_env("ETH_ADDRESS")

    if trx_address:
        addresses.setdefault("USDT", {})["TRC20"] = trx_address
    if bnb_address:
        addresses.setdefault("USDT", {})["BEP20"] = bnb_address
        addresses.setdefault("ETH", {})["BEP20"] = bnb_address
    if eth_address:
        addresses.setdefault("USDT", {})["ERC20"] = eth_address
        addresses.setdefault("ETH", {})["ERC20"] = eth_address
    return addresses


def load_settings() -> Settings:
    if load_dotenv:
        load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required. Copy .env.example to .env and configure it.")

    return Settings(
        bot_token=bot_token,
        database_url=_normalize_database_url(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./marco_bot.sqlite3").strip()),
        admin_ids=_split_ints(os.getenv("ADMIN_IDS")),
        admin_review_chat_id=os.getenv("ADMIN_REVIEW_CHAT_ID", "").strip() or None,
        ads_channel_id=os.getenv("ADS_CHANNEL_ID", "").strip() or None,
        ads_group_id=os.getenv("ADS_GROUP_ID", "").strip() or None,
        required_groups=_required_groups_from_env(),
        post_ad_cooldown_seconds=int(os.getenv("POST_AD_COOLDOWN_SECONDS", "10800")),
        timezone=os.getenv("TIMEZONE", "Asia/Kolkata").strip(),
        support_url=os.getenv("SUPPORT_URL", "https://t.me/MARCO_Escrow_Chat").strip(),
        banner_image_path=_optional_path(os.getenv("BANNER_IMAGE_PATH")),
        deposit_addresses=_deposit_addresses_from_env(),
        trx_address=_optional_env("TRX_ADDRESS"),
        bnb_address=_optional_env("BNB_ADDRESS"),
        eth_address=_optional_env("ETH_ADDRESS"),
        etherscan_api_key=_optional_env("ETHERSCAN_API_KEY"),
        infura_url=_optional_env("INFURA_URL"),
        infura_api_key=_optional_env("INFURA_API_KEY"),
        trongrid_api_key=_optional_env("TRONGRID_API_KEY"),
        telegram_api_id=_optional_env("TELEGRAM_API_ID"),
        telegram_api_hash=_optional_env("TELEGRAM_API_HASH"),
        telegram_phone=_optional_env("TELEGRAM_PHONE"),
    )
