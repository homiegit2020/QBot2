from __future__ import annotations

from decimal import Decimal

from marco_bot.config import Settings, _deposit_addresses_from_env, _normalize_database_url
from marco_bot.services import brand_banner_file, deposit_address, parse_decimal, safe_sell_banner_file


def settings_for_test(**overrides) -> Settings:
    values = dict(
        bot_token="123456:ABC",
        database_url="sqlite+aiosqlite:///./test.sqlite3",
        admin_ids=[],
        admin_review_chat_id=None,
        ads_channel_id=None,
        ads_group_id=None,
        required_groups=[],
        post_ad_cooldown_seconds=10800,
        timezone="Asia/Kolkata",
        support_url="https://t.me/MARCO_Escrow_Chat",
        banner_image_path=None,
        deposit_addresses={},
        trx_address=None,
        bnb_address=None,
        eth_address=None,
        etherscan_api_key=None,
        infura_url=None,
        infura_api_key=None,
        trongrid_api_key=None,
        telegram_api_id=None,
        telegram_api_hash=None,
        telegram_phone=None,
    )
    values.update(overrides)
    return Settings(**values)


def test_parse_decimal_accepts_commas() -> None:
    assert parse_decimal("1,234.50") == Decimal("1234.50")


def test_deposit_address_uses_configured_value() -> None:
    settings = settings_for_test(deposit_addresses={"USDT": {"BEP20": "0xabc"}})
    assert deposit_address(settings, "USDT", "BEP20") == "0xabc"
    assert deposit_address(settings, "USDT", "TRC20") == "CONFIGURE_USDT_TRC20_ADDRESS"


def test_brand_banner_file_is_png() -> None:
    banner = brand_banner_file()
    assert banner.filename == "marco-p2p-banner.png"


def test_safe_sell_banner_file_is_png() -> None:
    banner = safe_sell_banner_file()
    assert banner.filename == "marco-safe-sell-banner.png"


def test_railway_postgres_url_is_normalized() -> None:
    assert _normalize_database_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_direct_address_env_is_merged(monkeypatch) -> None:
    monkeypatch.setenv("DEPOSIT_ADDRESSES_JSON", "{}")
    monkeypatch.setenv("TRX_ADDRESS", "Tdemo")
    monkeypatch.setenv("BNB_ADDRESS", "0xbnb")
    monkeypatch.setenv("ETH_ADDRESS", "0xeth")
    addresses = _deposit_addresses_from_env()
    assert addresses["USDT"]["TRC20"] == "Tdemo"
    assert addresses["USDT"]["BEP20"] == "0xbnb"
    assert addresses["USDT"]["ERC20"] == "0xeth"
