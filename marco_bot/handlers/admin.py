from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.enums import MessageEntityType
from aiogram.types import CallbackQuery, Message, MessageEntity
from sqlalchemy import select

from .. import keyboards as kb
from .. import messages as msg
from ..config import Settings
from ..db import session_scope
from ..models import GlobalStats, PaymentMode, RateTier, Transaction, User, utcnow
from ..services import add_safe_sell_stats, as_money, parse_decimal, reset_today_if_needed

router = Router()
_settings: Settings | None = None


def configure(settings: Settings) -> None:
    global _settings
    _settings = settings


def settings() -> Settings:
    if _settings is None:
        raise RuntimeError("Admin router is not configured.")
    return _settings


def is_admin(user_id: int) -> bool:
    return user_id in settings().admin_ids


def _custom_emoji_ids(entities: list[MessageEntity] | None) -> list[str]:
    ids: list[str] = []
    for entity in entities or []:
        if entity.type == MessageEntityType.CUSTOM_EMOJI and entity.custom_emoji_id:
            ids.append(entity.custom_emoji_id)
    return ids


def extract_custom_emoji_ids(message: Message) -> list[str]:
    ids: list[str] = []
    ids.extend(_custom_emoji_ids(message.entities))
    ids.extend(_custom_emoji_ids(message.caption_entities))
    if message.reply_to_message:
        ids.extend(_custom_emoji_ids(message.reply_to_message.entities))
        ids.extend(_custom_emoji_ids(message.reply_to_message.caption_entities))
    unique_ids: list[str] = []
    for emoji_id in ids:
        if emoji_id not in unique_ids:
            unique_ids.append(emoji_id)
    return unique_ids


@router.message(Command("admin"))
async def admin_help(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    await message.answer(
        """MARCO Admin

/pending - show pending review queue
/stats - show global stats
/mode UPI on|off - toggle payment mode
/rates - show exchange tiers
/setrate UPI 10 600 94.0 - add/update a tier
/emojiids - extract premium custom emoji IDs from a message or reply
/broadcast message text - send to all users"""
    )


@router.message(Command("emojiids"))
async def emoji_ids(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    emoji_ids = extract_custom_emoji_ids(message)
    if not emoji_ids:
        await message.answer(
            "Send /emojiids as a reply to a message that contains premium emojis, or include the premium emojis in the same message."
        )
        return
    lines = ["Custom emoji IDs:"]
    for emoji_id in emoji_ids:
        lines.append(emoji_id)
    await message.answer("\n".join(lines))


@router.message(Command("pending"))
async def pending(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    async with session_scope() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.status == "pending")
            .order_by(Transaction.created_at)
            .limit(20)
        )
        rows = result.scalars().all()
        if not rows:
            await message.answer("No pending transactions.")
            return
        lines = ["Pending transactions:"]
        for tx in rows:
            lines.append(f"TX {tx.tx_id} | {tx.type} | user {tx.user_id} | ${tx.amount_usd:.2f}")
        await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def admin_stats(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    async with session_scope() as session:
        stats = await session.get(GlobalStats, 1)
        if not stats:
            stats = GlobalStats(id=1)
            session.add(stats)
            await session.flush()
        await reset_today_if_needed(session, stats, settings().timezone)
        await message.answer(msg.global_stats(stats.total_safe_sold_amount, stats.today_safe_sold_amount, stats.total_deals_completed))


@router.message(Command("mode"))
async def mode_toggle(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[2].lower() not in {"on", "off"}:
        await message.answer("Usage: /mode UPI on|off")
        return
    payment_mode = parts[1].upper()
    available = parts[2].lower() == "on"
    async with session_scope() as session:
        mode = await session.get(PaymentMode, payment_mode)
        if not mode:
            mode = PaymentMode(payment_mode=payment_mode, available=available)
            session.add(mode)
        mode.available = available
        flag = "🟢 Available" if available else "🔴 Unavailable"
        await message.answer(f"{payment_mode} is now {flag}.")


@router.message(Command("rates"))
async def rates(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    async with session_scope() as session:
        result = await session.execute(select(RateTier).order_by(RateTier.payment_mode, RateTier.min_usd))
        rows = result.scalars().all()
        if not rows:
            await message.answer("No rate tiers configured.")
            return
        lines = ["Rate tiers:"]
        for tier in rows:
            maximum = "+" if tier.max_usd is None else f"-${tier.max_usd:.0f}"
            lines.append(f"{tier.payment_mode}: ${tier.min_usd:.0f}{maximum} = {tier.rate_inr:.1f}₹")
        await message.answer("\n".join(lines))


@router.message(Command("setrate"))
async def set_rate(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 5:
        await message.answer("Usage: /setrate UPI 10 600 94.0 (use + for open-ended max)")
        return
    payment_mode = parts[1].upper()
    min_usd = parse_decimal(parts[2])
    max_usd = None if parts[3] == "+" else parse_decimal(parts[3])
    rate = parse_decimal(parts[4])
    if min_usd is None or rate is None or (parts[3] != "+" and max_usd is None):
        await message.answer("Invalid numeric rate tier.")
        return
    async with session_scope() as session:
        result = await session.execute(
            select(RateTier).where(
                RateTier.payment_mode == payment_mode,
                RateTier.min_usd == min_usd,
                RateTier.max_usd == max_usd,
            )
        )
        tier = result.scalar_one_or_none()
        if not tier:
            tier = RateTier(payment_mode=payment_mode, min_usd=min_usd, max_usd=max_usd, rate_inr=rate)
            session.add(tier)
        else:
            tier.rate_inr = rate
        await message.answer(f"Saved {payment_mode} tier at {rate:.1f}₹.")


@router.message(Command("broadcast"))
async def broadcast(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Usage: /broadcast message text")
        return
    sent = 0
    async with session_scope() as session:
        result = await session.execute(select(User.user_id))
        user_ids = [row[0] for row in result.all()]
    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, text)
            sent += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            continue
    await message.answer(f"Broadcast sent to {sent} users.")


@router.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.data:
        return
    if not is_admin(callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    try:
        _, action, tx_id_raw = callback.data.split(":", 2)
        tx_id = int(tx_id_raw)
    except ValueError:
        await callback.answer("Invalid admin action.", show_alert=True)
        return

    if action == "approve":
        await approve_transaction(callback, tx_id)
    elif action == "reject":
        await reject_transaction(callback, tx_id)
    else:
        await callback.answer("Unknown admin action.", show_alert=True)


async def approve_transaction(callback: CallbackQuery, tx_id: int) -> None:
    async with session_scope() as session:
        tx = await session.get(Transaction, tx_id)
        if not tx or tx.status != "pending":
            await callback.answer("Transaction is not pending.", show_alert=True)
            return
        user = await session.get(User, tx.user_id)
        if not user:
            await callback.answer("User not found.", show_alert=True)
            return

        if tx.type == "withdrawal":
            if user.wallet_balance < tx.amount_usd:
                await callback.answer("Insufficient user wallet balance.", show_alert=True)
                return
            user.wallet_balance = as_money(user.wallet_balance - tx.amount_usd)
        elif tx.type in {"express_sell", "wallet_deposit"}:
            if tx.type == "wallet_deposit":
                user.wallet_balance = as_money(user.wallet_balance + tx.amount_usd)
            await add_safe_sell_stats(session, user, tx.amount_usd, settings().timezone)

        tx.status = "approved"
        tx.admin_id = callback.from_user.id
        tx.resolved_at = utcnow()
        user.is_locked = False
        await notify_user_approved(callback, user, tx)
        await callback.answer("Approved.")
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.answer(f"✅ TX {tx.tx_id} approved by {callback.from_user.id}.")
            except TelegramBadRequest:
                pass


async def reject_transaction(callback: CallbackQuery, tx_id: int) -> None:
    async with session_scope() as session:
        tx = await session.get(Transaction, tx_id)
        if not tx or tx.status != "pending":
            await callback.answer("Transaction is not pending.", show_alert=True)
            return
        user = await session.get(User, tx.user_id)
        if not user:
            await callback.answer("User not found.", show_alert=True)
            return
        tx.status = "rejected"
        tx.admin_id = callback.from_user.id
        tx.resolved_at = utcnow()
        user.is_locked = False
        await notify_user_rejected(callback, user, tx)
        await callback.answer("Rejected.")
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.answer(f"❌ TX {tx.tx_id} rejected by {callback.from_user.id}.")
            except TelegramBadRequest:
                pass


async def notify_user_approved(callback: CallbackQuery, user: User, tx: Transaction) -> None:
    if tx.type == "withdrawal":
        text = "✅ Withdrawal Approved!\n\nYour payout request has been marked completed."
    elif tx.type == "wallet_deposit":
        text = f"✅ Payment Verified!\n\n${tx.amount_usd:.2f} has been added to your wallet balance."
    else:
        text = "✅ Payment Verified!\n\nYour transaction has been approved. SAFE & GUARANTEED INR payout is marked completed."
    try:
        await callback.bot.send_message(user.user_id, text, reply_markup=kb.persistent_menu(user))
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


async def notify_user_rejected(callback: CallbackQuery, user: User, tx: Transaction) -> None:
    text = "❌ Payment Rejected!\n\nPlease retry or contact support."
    if tx.type == "withdrawal":
        text = "❌ Withdrawal Rejected!\n\nPlease retry or contact support."
    try:
        await callback.bot.send_message(user.user_id, text, reply_markup=kb.persistent_menu(user))
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
