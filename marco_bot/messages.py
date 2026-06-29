from __future__ import annotations

from decimal import Decimal

from .constants import (
    ADS_CHANNEL_USERNAME,
    BOT_USERNAME,
    ESCROW_BOT_USERNAME,
    ESCROW_CHAT_USERNAME,
    IN_AD_ESCROW_USERNAME,
    UPDATES_USERNAME,
)

INFO_CARD = f"""What can this bot do? ⚡

⚡ Instant Crypto Sell
💎 Trusted & Safe MARCO Platform
🤑 SAFE Guaranteed INR Payouts
📢 Post P2P Ads On {ADS_CHANNEL_USERNAME}

Escrow : {ESCROW_BOT_USERNAME}
Chat : {ESCROW_CHAT_USERNAME}
Updates : {UPDATES_USERNAME}"""

WELCOME = """<tg-emoji emoji-id="5994297722574737553">💬</tg-emoji> Welcome to MARCO P2P Bot

<tg-emoji emoji-id="5197434882321567830">💵</tg-emoji> SAFE SELL — A trusted platform to Sell Crypto <tg-emoji emoji-id="4911320645146510335">🔥</tg-emoji> Instantly and receive SAFE & GUARANTEED INR ₹ directly <tg-emoji emoji-id="5832546462478635761">🔒</tg-emoji>

Choose an option below to get started <tg-emoji emoji-id="6105102145030199285">👇</tg-emoji>"""

GROUP_GATE = """❌ Access Denied 🔒

To post ads, you must be a member of both our groups:
1️⃣ Join Group 1
2️⃣ Join Group 2

After joining, click POST AD again ⚡"""


def captcha_caption(first_name: str) -> str:
    return f"""Welcome! {first_name} 👋

To Join MARCO P2P 🔥, Solve this Captcha to get accepted! ⚡"""


def captcha_accepted(first_name: str) -> str:
    return f"""{first_name} You are accepted!!! ✅
Welcome To MARCO P2P 🔥

Use /start to sell your crypto right away! ⚡"""


def premium_emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


OBJECTIVE = f"{premium_emoji('5240086656349913841', '🤑')} What would you like to do?"
COIN_SELECT = f"{premium_emoji('5778311685638984859', '🪙')} Choose Your Coin:"


def chain_select(coin: str) -> str:
    return f"<tg-emoji emoji-id='5411246291416013236'>🔗</tg-emoji> Select Chain for {coin}"


FUNDS_SOURCE = "<tg-emoji emoji-id='5348503265967355284'>💰</tg-emoji> Choose payment source"


def rate_input(category: str, minimum: float, maximum: float) -> str:
    return f"""<tg-emoji emoji-id='5927169041595634481'>💳</tg-emoji> Set exchange rate
Category: {category}
Enter a number between {minimum:.1f} and {maximum:.1f}:"""


AMOUNT_INPUT = "▽ Enter amount / quantity ⚡\n(e.g 10-100-1000)"
PAYMENT_METHOD = "<tg-emoji emoji-id='5967389567781703494'>💼</tg-emoji> Pick a payment method"


def ad_text(data: dict, username: str, preview: bool = True) -> str:
    side = data.get("side", "sell")
    if side == "sell":
        side_line = "<tg-emoji emoji-id='5972265777296838427'>💵</tg-emoji> #Selling"
    else:
        side_line = "<tg-emoji emoji-id='5852871561983299073'>🛒</tg-emoji> #Buying"
    header = "🔍 ADVERTISEMENT PREVIEW\n\n" if preview else ""
    return f"""{header}{side_line}

<tg-emoji emoji-id='5832251986635920010'>💎</tg-emoji> Crypto: {data.get("coin")}
<tg-emoji emoji-id='5992430854909989581'>💰</tg-emoji> Quantity: {data.get("amount")}$
<tg-emoji emoji-id='5987917196469213507'>🔗</tg-emoji> Chain: {data.get("chain")}
<tg-emoji emoji-id='5926783847453692661'>🏦</tg-emoji> Funds Source: {data.get("funds_source")}
<tg-emoji emoji-id='5974217466270716579'>📈</tg-emoji> Rate: {data.get("rate")}
<tg-emoji emoji-id='5967548335542767952'>💳</tg-emoji> Payment Method: {data.get("payment_method")}

<tg-emoji emoji-id='5886412370347036129'>👤</tg-emoji> DM: @{username}
<tg-emoji emoji-id='6034962180875490251'>⚖️</tg-emoji> Escrow: {IN_AD_ESCROW_USERNAME}"""


def ad_published(ref_code: str) -> str:
    return f"""🚀 Ad Published Successfully! 🔥

Your ad is now live in the channel post.
Ref: {ref_code}

Use {BOT_USERNAME} for SAFE-SELL ⚡"""


SAFE_SELL_LANDING = """Welcome to MARCO P2P Bot 👋⚡️

SAFE SELL — A trusted platform to Sell Crypto Instantly and receive SAFE & GUARANTEED INR ₹ directly.

Choose an option below to get started 👇"""

SAFE_SELL_BANNER = """✔ Instant Payments ⚡
✔ Verified & Guaranteed Funds
✔ Supported Modes – UPI | IMPS | CDM
✔ No Time-passers | No Scams
✔ Direct SAFE-SELL to us & relax

Fund Purity & Safety — Guaranteed by MARCO 🔥
Each penny you receive is 100% authentic & Guaranteed!"""

PAYMENT_MODE_SELECT = "Sell your crypto in multiple methods 👇⚡"


def exchange_rates(payment_mode: str, tiers: list[tuple[Decimal, Decimal | None, Decimal]]) -> str:
    lines = []
    for min_usd, max_usd, rate in tiers:
        if max_usd is None:
            band = f"${min_usd:.0f}+"
        else:
            band = f"${min_usd:.0f}-${max_usd:.0f}"
        lines.append(f"▪ {band} : {rate:.1f}₹")
    tier_text = "\n".join(lines)
    return f"""Important - You may get funds in multiple shots, if the order is bigger than 25K₹⚡ (100% Safe)

EXCHANGE RATES FOR {payment_mode} 👇

{tier_text}

Enter Amount in $ you want to sell :"""


def inr_preview(amount_inr: Decimal) -> str:
    return f"""You will receive approx: ₹{amount_inr:.2f} 💰

Select Your Crypto Token 👇"""


def express_chain_select(token: str) -> str:
    return f"Select Network Chain for {token} ⚡:"


def deposit_instructions(token: str, chain: str, address: str) -> str:
    return f"""💎 Token: {token}
🔗 Network: {chain}

Pay on the address below 👇:
{address}

⚠ Note: Send exact amount or more. Any extra will be added to your wallet balance.

After payment, click 'CHECK PAYMENT' below to send proof ⚡"""


SCREENSHOT_PROMPT = "Please send a screenshot of your payment for verification 📸."


SCREENSHOT_SUBMITTED = """✅ Screenshot Submitted!

Please wait for admin verification ⚡"""

LOCKED_ACTION = "⚠ This action is disabled pending transaction verification 🔒."

LOCKED_STATS = """⚠ Verification Pending 🔒.
Account is currently locked."""


def wallet(balance: Decimal) -> str:
    return f"""<tg-emoji emoji-id='5444856076954520455'>🧾</tg-emoji> Your Wallet Balance

<tg-emoji emoji-id='5287231198098117669'>💰</tg-emoji> Available: ${balance:.2f} USD

You can deposit funds to use later or withdraw your funds at any time"""


def my_stats(username: str, member_since: str, ads: int, sells: int, volume: Decimal) -> str:
    return f"""<tg-emoji emoji-id='5913702317667913862'>📊</tg-emoji> @{username} Statistics

<tg-emoji emoji-id='5936130851635990622'>▪️</tg-emoji> Member Since: {member_since}
<tg-emoji emoji-id='5936130851635990622'>▪️</tg-emoji> P2P Ads Posted: {ads}
<tg-emoji emoji-id='5936130851635990622'>▪️</tg-emoji> Safe Sells Completed: {sells}
<tg-emoji emoji-id='5936130851635990622'>▪️</tg-emoji> Total Safe Sell Volume: ${volume:.2f}

Use {BOT_USERNAME} for SAFE-SELL <tg-emoji emoji-id='5408892168301466942'>🔥</tg-emoji>"""


def global_stats(total: Decimal, today: Decimal, deals: int) -> str:
    return f"""<tg-emoji emoji-id='5913702317667913862'>📊</tg-emoji> Global Stats Of {BOT_USERNAME}

<tg-emoji emoji-id='5987880246865565644'>💰</tg-emoji> Total SAFE-SOLD Amount:
${total:,.2f}

<tg-emoji emoji-id='5217604963571621845'>📅</tg-emoji> Today's SAFE-SOLD Amount:
${today:,.2f}

<tg-emoji emoji-id='5408892168301466942'>🔥</tg-emoji> Total SAFE-SOLD Deals
Completed:
{deals}

<tg-emoji emoji-id='5877485980901971030'>💎</tg-emoji> Always use {BOT_USERNAME} to get safest INR₹ in exchange!
<tg-emoji emoji-id='5409099658171537510'>📊</tg-emoji> This Data shows how much crypto users have SOLD US!"""


WITHDRAW_AMOUNT = "💵 Enter withdrawal amount in USD ⚡:"
WITHDRAW_DESTINATION = "📤 Send your withdrawal destination (UPI ID / bank details / crypto address):"
WALLET_ADD_AMOUNT = "💰 Enter Amount in $ you want to add ⚡ :"


def withdraw_queued(tx_id: int) -> str:
    return f"""✅ Withdrawal request submitted! 💸

Please wait for admin payout ⚡.
Ref: TX-{tx_id}"""
