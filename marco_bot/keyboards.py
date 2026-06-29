from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from . import constants as c
from .models import PaymentMode, RequiredGroup, User
from .services import format_remaining, random_code


def persistent_menu(user: User | None = None) -> ReplyKeyboardMarkup:
    post_label = c.POST_AD_BUTTON
    if user and user.post_ad_cooldown_until and user.post_ad_cooldown_until > datetime.utcnow():
        post_label = f"POST AD ⏳ ({format_remaining(user.post_ad_cooldown_until)})"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=post_label), KeyboardButton(text=c.SAFE_SELL_BUTTON)],
            [KeyboardButton(text=c.WALLET_BUTTON), KeyboardButton(text=c.MY_STATS_BUTTON)],
            [KeyboardButton(text=c.GLOBAL_STATS_BUTTON)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def start_bot() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Start Bot", callback_data="start_bot")]])


def group_gate(groups: list[RequiredGroup]) -> InlineKeyboardMarkup | None:
    if not groups:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=group.label, url=group.invite_link)]
            for group in groups
        ]
    )


def captcha_options(code: str) -> InlineKeyboardMarkup:
    options = {code}
    while len(options) < 4:
        options.add(random_code(len(code)))
    ordered = list(options)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=ordered[0], callback_data=f"captcha:answer:{ordered[0]}"),
                InlineKeyboardButton(text=ordered[1], callback_data=f"captcha:answer:{ordered[1]}"),
            ],
            [
                InlineKeyboardButton(text=ordered[2], callback_data=f"captcha:answer:{ordered[2]}"),
                InlineKeyboardButton(text=ordered[3], callback_data=f"captcha:answer:{ordered[3]}"),
            ],
        ]
    )


def back(callback_data: str = "nav:back", text: str = c.BACK_BUTTON) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])


def objective() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Buy", callback_data="ad:side:buy"),
                InlineKeyboardButton(text="🔴 Sell", callback_data="ad:side:sell"),
            ],
            [InlineKeyboardButton(text=c.BACK_TO_MENU_BUTTON, callback_data="nav:menu")],
        ]
    )


def coin_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="USDT", callback_data="ad:coin:USDT"), InlineKeyboardButton(text="BTC", callback_data="ad:coin:BTC")],
            [InlineKeyboardButton(text="SOL", callback_data="ad:coin:SOL"), InlineKeyboardButton(text="ETH", callback_data="ad:coin:ETH")],
            [InlineKeyboardButton(text="USDC", callback_data="ad:coin:USDC")],
            [InlineKeyboardButton(text=c.BACK_BUTTON, callback_data="nav:back")],
        ]
    )


def chains(coin: str, prefix: str = "ad") -> InlineKeyboardMarkup:
    options = c.USDT_CHAINS if coin == "USDT" else c.DEFAULT_CHAINS
    if coin == "BTC":
        options = c.BTC_CHAINS
    elif coin == "ETH":
        options = c.ETH_CHAINS
    elif coin == "SOL":
        options = c.SOL_CHAINS
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(0, len(options), 2):
        rows.append(
            [
                InlineKeyboardButton(text=name, callback_data=f"{prefix}:chain:{name}")
                for name in options[idx : idx + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text=c.BACK_BUTTON, callback_data="nav:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def express_chains(token: str, prefix: str = "express") -> InlineKeyboardMarkup:
    options = c.EXPRESS_USDT_CHAINS if token == "USDT" else c.DEFAULT_CHAINS
    if token == "BTC":
        options = c.BTC_CHAINS
    elif token == "ETH":
        options = ["BEP20", "ERC20", "MATIC", "TRC20"]
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(0, len(options), 2):
        rows.append(
            [
                InlineKeyboardButton(text=name, callback_data=f"{prefix}:chain:{name}")
                for name in options[idx : idx + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def funds_source() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Legit", callback_data="ad:source:Legit"), InlineKeyboardButton(text="Layer2", callback_data="ad:source:Layer2")],
            [InlineKeyboardButton(text="Stock", callback_data="ad:source:Stock"), InlineKeyboardButton(text="Gaming", callback_data="ad:source:Gaming")],
            [InlineKeyboardButton(text="Mix", callback_data="ad:source:Mix")],
            [InlineKeyboardButton(text=c.BACK_BUTTON, callback_data="nav:back")],
        ]
    )


def quick_amount(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="100%" if prefix != "ad" else "0%", callback_data=f"{prefix}:quick:100p"),
                InlineKeyboardButton(text="1000", callback_data=f"{prefix}:quick:1000"),
                InlineKeyboardButton(text="100", callback_data=f"{prefix}:quick:100"),
            ],
            [InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON if prefix != "ad" else c.BACK_BUTTON, callback_data="nav:back")],
        ]
    )


def payment_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="UPI/IMPS", callback_data="ad:method:UPI/IMPS"), InlineKeyboardButton(text="CDM", callback_data="ad:method:CDM")],
            [InlineKeyboardButton(text="Cardless", callback_data="ad:method:Cardless"), InlineKeyboardButton(text="IMPS/RTGS", callback_data="ad:method:IMPS/RTGS")],
            [InlineKeyboardButton(text=c.BACK_BUTTON, callback_data="nav:back")],
        ]
    )


def ad_preview() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍ Revise Ad", callback_data="ad:revise"),
                InlineKeyboardButton(text="🚀 Publish Ad", callback_data="ad:publish"),
            ]
        ]
    )


def express_landing(balance: Decimal, support_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="SELL CRYPTO ⚡️", callback_data="express:sell")],
            [InlineKeyboardButton(text="Saved Payment Methods", callback_data="express:saved_methods")],
            [InlineKeyboardButton(text=f"💰 Balance: ${balance:.2f}", callback_data="wallet:open")],
            [InlineKeyboardButton(text="Support", url=support_url)],
            [InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:menu")],
        ]
    )


def payment_modes(modes: list[PaymentMode]) -> InlineKeyboardMarkup:
    mode_map = {mode.payment_mode: mode.available for mode in modes}
    rows = []
    for mode, icon in [("UPI", "📱"), ("IMPS", "🏦"), ("CDM", "🏛")]:
        available = mode_map.get(mode, True)
        flag = "🟢 Available" if available else "🔴 Unavailable"
        rows.append([InlineKeyboardButton(text=f"{mode} {icon} ({flag})", callback_data=f"express:mode:{mode}")])
    rows.append([InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def token_select(prefix: str = "express") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="BTC", callback_data=f"{prefix}:token:BTC"), InlineKeyboardButton(text="ETH", callback_data=f"{prefix}:token:ETH")],
            [InlineKeyboardButton(text="USDT", callback_data=f"{prefix}:token:USDT")],
            [InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:back")],
        ]
    )


def check_payment() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="CHECK PAYMENT ✅", callback_data="payment:check")],
            [InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:back")],
        ]
    )


def wallet_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add Funds ➕💵", callback_data="wallet:add")],
            [InlineKeyboardButton(text="Withdraw Funds 💸", callback_data="wallet:withdraw")],
            [InlineKeyboardButton(text=c.BACK_PLAIN_BUTTON, callback_data="nav:menu")],
        ]
    )


def admin_review(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve ✅", callback_data=f"admin:approve:{tx_id}"),
                InlineKeyboardButton(text="Reject ❌", callback_data=f"admin:reject:{tx_id}"),
            ]
        ]
    )
