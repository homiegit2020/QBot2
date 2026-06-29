from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, select

from .. import constants as c
from .. import keyboards as kb
from .. import messages as msg
from .. import states
from ..config import Settings
from ..db import session_scope
from ..models import Ad, CaptchaAttempt, GlobalStats, PaymentMode, Transaction, User, utcnow
from ..services import (
    add_safe_sell_stats,
    as_money,
    captcha_file,
    clear_flow,
    delete_active_menu_message,
    deposit_address,
    format_remaining,
    get_or_create_session,
    get_or_create_user,
    get_rate_tiers,
    parse_decimal,
    pop_state,
    public_username,
    random_captcha,
    random_code,
    rate_for_amount,
    required_groups,
    reset_today_if_needed,
    safe_sell_banner_file,
    save_captcha,
    send_brand_message,
    send_tracked_menu_message,
    send_tracked_menu_photo,
    session_data,
    set_state,
    telegram_username,
    transition,
    user_is_in_required_groups,
)

router = Router()
_settings: Settings | None = None


def configure(settings: Settings) -> None:
    global _settings
    _settings = settings


def settings() -> Settings:
    if _settings is None:
        raise RuntimeError("User router is not configured.")
    return _settings


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    if not message.from_user:
        return
    async with session_scope() as session:
        user, created = await get_or_create_user(session, message.from_user)
        await clear_flow(session, user.user_id)
        if created:
            await send_brand_message(
                message.bot,
                message.chat.id,
                msg.INFO_CARD,
                settings(),
                reply_markup=kb.start_bot(),
                session=session,
                user_id=user.user_id,
            )
        else:
            await send_welcome(message, user)


@router.message(Command("stats"))
async def command_stats(message: Message) -> None:
    await show_global_stats(message)


@router.message(Command("p2pstats"))
async def command_p2pstats(message: Message) -> None:
    if not message.from_user:
        return
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, message.from_user)
    await show_my_stats(message, user)


@router.message(Command("cancel"))
async def command_cancel(message: Message) -> None:
    if not message.from_user:
        return
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        await clear_flow(session, user.user_id)
    await send_welcome(message, user)


@router.callback_query(F.data == "start_bot")
async def start_bot_callback(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        await clear_flow(session, user.user_id)
        await delete_callback_message(callback)
        await callback.answer()
        await send_welcome(callback.message, user)


@router.message(F.photo)
async def proof_photo(message: Message) -> None:
    if not message.from_user:
        return
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        bot_session = await get_or_create_session(session, user.user_id)
        if bot_session.state not in {states.EXPRESS_AWAITING_SCREENSHOT, states.WALLET_AWAITING_SCREENSHOT}:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Please use the bot buttons to start a payment flow.", reply_markup=kb.persistent_menu(user))
            return

        data = session_data(bot_session)
        proof = message.photo[-1].file_id
        tx_type = data.get("tx_type", "express_sell")
        tx = Transaction(
            user_id=user.user_id,
            type=tx_type,
            coin=data.get("token"),
            chain=data.get("chain"),
            amount_usd=Decimal(str(data.get("amount_usd", "0"))),
            amount_inr=Decimal(str(data.get("amount_inr", "0"))),
            payment_mode=data.get("payment_mode"),
            deposit_address=data.get("deposit_address"),
            proof_file_id=proof,
            status="pending",
        )
        session.add(tx)
        user.is_locked = True
        await clear_flow(session, user.user_id)
        await session.flush()
        await notify_admin_review(message, user, tx)
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.SCREENSHOT_SUBMITTED, reply_markup=kb.persistent_menu(user))


@router.message(F.text)
async def text_message(message: Message) -> None:
    if not message.from_user or not message.text:
        return
    text = message.text.strip()
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        bot_session = await get_or_create_session(session, user.user_id)
        state = bot_session.state
        locked = user.is_locked

    if is_global_stats(text):
        await show_global_stats(message)
        return

    if locked and is_locked_entry(text):
        await show_locked_for_text(message, text, user)
        return

    if is_post_ad(text):
        await enter_post_ad(message, user)
        return
    if text == c.SAFE_SELL_BUTTON:
        await enter_safe_sell(message, user)
        return
    if text == c.WALLET_BUTTON:
        await open_wallet(message, user)
        return
    if text == c.MY_STATS_BUTTON:
        await show_my_stats(message, user)
        return

    if state == states.CAPTCHA:
        await handle_captcha_answer(message, user, text)
    elif state == states.AD_RATE_INPUT:
        await handle_ad_rate(message, user, text)
    elif state == states.AD_AMOUNT_INPUT:
        await handle_ad_amount(message, user, text)
    elif state == states.EXPRESS_AMOUNT_INPUT:
        await handle_express_amount(message, user, text)
    elif state == states.WALLET_ADD_AMOUNT:
        await handle_wallet_deposit_amount(message, user, text)
    elif state == states.WALLET_WITHDRAW_AMOUNT:
        await handle_withdraw_amount(message, user, text)
    elif state == states.WALLET_WITHDRAW_DEST:
        await handle_withdraw_destination(message, user, text)
    else:
        await send_welcome(message, user)


@router.callback_query()
async def callbacks(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return
    if callback.data.startswith("admin:"):
        return
    async with session_scope() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        data = callback.data
        locked = user.is_locked

    if data == "nav:menu":
        async with session_scope() as session:
            await clear_flow(session, user.user_id)
        await delete_callback_message(callback)
        await callback.answer()
        await send_welcome(callback.message, user)
        return
    if data == "nav:back":
        async with session_scope() as session:
            bot_session = await pop_state(session, user.user_id)
            state = bot_session.state
        await delete_callback_message(callback)
        await callback.answer()
        await render_state(callback.message, user, state)
        return
    if data.startswith("captcha:answer:"):
        await callback.answer()
        await handle_captcha_answer(callback.message, user, data.rsplit(":", 1)[1])
        return
    if locked and data not in {"wallet:open"}:
        await callback.answer(msg.LOCKED_ACTION, show_alert=True)
        return

    if data.startswith("ad:side:"):
        await set_ad_side(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("ad:coin:"):
        await set_ad_coin(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("ad:chain:"):
        await set_ad_chain(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("ad:source:"):
        await set_ad_source(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("ad:quick:"):
        await handle_quick_amount(callback, user, "ad", data.rsplit(":", 1)[1])
    elif data.startswith("ad:method:"):
        await set_ad_method(callback, user, data.split(":", 2)[2])
    elif data == "ad:revise":
        await revise_ad(callback, user)
    elif data == "ad:publish":
        await publish_ad(callback, user)
    elif data == "express:sell":
        await show_payment_modes(callback, user)
    elif data == "express:saved_methods":
        await callback.answer("Saved Payment Methods are not configured yet.", show_alert=True)
    elif data.startswith("express:mode:"):
        await set_express_mode(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("express:quick:"):
        await handle_quick_amount(callback, user, "express", data.rsplit(":", 1)[1])
    elif data.startswith("express:token:"):
        await set_express_token(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("express:chain:"):
        await set_express_chain(callback, user, data.rsplit(":", 1)[1])
    elif data == "payment:check":
        await request_screenshot(callback, user)
    elif data == "wallet:open":
        await delete_callback_message(callback)
        await open_wallet(callback.message, user)
        await callback.answer()
    elif data == "wallet:add":
        await wallet_add(callback, user)
    elif data == "wallet:withdraw":
        await wallet_withdraw(callback, user)
    elif data.startswith("wallet:token:"):
        await set_wallet_token(callback, user, data.rsplit(":", 1)[1])
    elif data.startswith("wallet:chain:"):
        await set_wallet_chain(callback, user, data.rsplit(":", 1)[1])
    else:
        await callback.answer()


def is_post_ad(text: str) -> bool:
    return text == c.POST_AD_BUTTON or text.startswith("POST AD ⏳")


def is_global_stats(text: str) -> bool:
    return text == c.GLOBAL_STATS_BUTTON


def is_locked_entry(text: str) -> bool:
    return text in {c.POST_AD_BUTTON, c.SAFE_SELL_BUTTON, c.WALLET_BUTTON, c.MY_STATS_BUTTON} or text.startswith("POST AD ⏳")


async def send_welcome(target: Message, user: User) -> None:
    async with session_scope() as session:
        await send_brand_message(
            target.bot,
            target.chat.id,
            msg.WELCOME,
            settings(),
            reply_markup=kb.persistent_menu(user),
            session=session,
            user_id=user.user_id,
        )


async def show_locked_for_text(message: Message, text: str, user: User) -> None:
    async with session_scope() as session:
        if text == c.MY_STATS_BUTTON:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_STATS, reply_markup=kb.persistent_menu(user))
        else:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_ACTION, reply_markup=kb.persistent_menu(user))


async def enter_post_ad(message: Message, user: User) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        assert user is not None
        if user.post_ad_cooldown_until and user.post_ad_cooldown_until > datetime.utcnow():
            await send_tracked_menu_message(
                session,
                message.bot,
                user.user_id,
                message.chat.id,
                f"POST AD is on cooldown. Try again in {format_remaining(user.post_ad_cooldown_until)}.",
                reply_markup=kb.persistent_menu(user),
            )
            return
        if user.is_locked:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_ACTION, reply_markup=kb.persistent_menu(user))
            return
        if not user.is_group_verified:
            if not await user_is_in_required_groups(message.bot, session, user.user_id):
                groups = await required_groups(session)
                await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.GROUP_GATE, reply_markup=kb.group_gate(groups))
                return
            await send_captcha(message, session, user)
            return
        await set_state(session, user.user_id, states.AD_SIDE_SELECT, data={}, stack=[states.IDLE])
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.OBJECTIVE, reply_markup=kb.objective(), parse_mode=ParseMode.HTML)


async def send_captcha(message: Message, session, user: User, reset_attempts: bool = True) -> None:
    code = random_captcha()
    await save_captcha(session, user.user_id, code, reset_attempts=reset_attempts)
    await set_state(session, user.user_id, states.CAPTCHA, data={}, stack=[states.IDLE])
    first_name = user.first_name or "Friend"
    await send_tracked_menu_photo(session, message.bot, user.user_id, message.chat.id, captcha_file(code), msg.captcha_caption(first_name), reply_markup=kb.captcha_options(code))


async def handle_captcha_answer(message: Message, user: User, text: str) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        attempt = await session.get(CaptchaAttempt, user.user_id)
        if not user:
            return
        if not attempt or attempt.expires_at < utcnow():
            await send_captcha(message, session, user)
            return
        if text.upper() == attempt.captcha_code:
            user.is_group_verified = True
            await session.execute(delete(CaptchaAttempt).where(CaptchaAttempt.user_id == user.user_id))
            await clear_flow(session, user.user_id)
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "✅ Captcha solved correctly!")
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.captcha_accepted(user.first_name or "Friend"), reply_markup=kb.persistent_menu(user))
            return

        attempt.attempts += 1
        if attempt.attempts >= 5:
            await session.execute(delete(CaptchaAttempt).where(CaptchaAttempt.user_id == user.user_id))
            await clear_flow(session, user.user_id)
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Captcha failed too many times. Please click POST AD again to retry.")
            return
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "❌ Incorrect captcha. Please try the new captcha.")
        await send_captcha(message, session, user, reset_attempts=False)


async def set_ad_side(callback: CallbackQuery, user: User, side: str) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.AD_COIN_SELECT, {"side": side}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.COIN_SELECT, reply_markup=kb.coin_select(), parse_mode=ParseMode.HTML)


async def set_ad_coin(callback: CallbackQuery, user: User, coin: str) -> None:
    async with session_scope() as session:
        bot_session = await transition(session, user.user_id, states.AD_CHAIN_SELECT, {"coin": coin}, push=True)
        data = session_data(bot_session)
        for key in ["chain", "funds_source", "rate", "amount", "payment_method"]:
            data.pop(key, None)
        bot_session.data_json = json.dumps(data)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.chain_select(coin), reply_markup=kb.chains(coin))


async def set_ad_chain(callback: CallbackQuery, user: User, chain: str) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.AD_FUNDS_SOURCE, {"chain": chain}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.FUNDS_SOURCE, reply_markup=kb.funds_source())


async def set_ad_source(callback: CallbackQuery, user: User, source: str) -> None:
    async with session_scope() as session:
        band = c.AD_RATE_BANDS.get(source, (94.0, 102.0))
        await transition(session, user.user_id, states.AD_RATE_INPUT, {"funds_source": source}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.rate_input(source, band[0], band[1]), reply_markup=kb.back())


async def handle_ad_rate(message: Message, user: User, text: str) -> None:
    rate = parse_decimal(text)
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        source = data.get("funds_source", "Legit")
        band = c.AD_RATE_BANDS.get(source, (94.0, 102.0))
        if rate is None or rate < Decimal(str(band[0])) or rate > Decimal(str(band[1])):
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.rate_input(source, band[0], band[1]), reply_markup=kb.back())
            return
        await transition(session, user.user_id, states.AD_AMOUNT_INPUT, {"rate": str(rate)}, push=True)
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.AMOUNT_INPUT, reply_markup=kb.quick_amount("ad"))


async def handle_ad_amount(message: Message, user: User, text: str) -> None:
    amount = parse_decimal(text)
    if amount is None or amount <= 0:
        async with session_scope() as session:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Enter a valid amount greater than 0.", reply_markup=kb.quick_amount("ad"))
        return
    async with session_scope() as session:
        await transition(session, user.user_id, states.AD_PAYMENT_METHOD, {"amount": str(amount)}, push=True)
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.PAYMENT_METHOD, reply_markup=kb.payment_methods())


async def handle_quick_amount(callback: CallbackQuery, user: User, prefix: str, value: str) -> None:
    amount = Decimal("1000") if value == "1000" else Decimal("100")
    if value == "100p":
        if prefix == "express":
            amount = Decimal("100")
        else:
            await callback.answer("Enter a valid amount manually.", show_alert=True)
            return
    if prefix == "ad":
        async with session_scope() as session:
            await transition(session, user.user_id, states.AD_PAYMENT_METHOD, {"amount": str(amount)}, push=True)
            await delete_callback_message(callback)
            await callback.answer()
            await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.PAYMENT_METHOD, reply_markup=kb.payment_methods())
    else:
        await process_express_amount(callback.message, user, amount)
        await delete_callback_message(callback)
        await callback.answer()


async def set_ad_method(callback: CallbackQuery, user: User, method: str) -> None:
    async with session_scope() as session:
        bot_session = await transition(session, user.user_id, states.AD_PREVIEW, {"payment_method": method}, push=True)
        data = session_data(bot_session)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.ad_text(data, public_username(user), preview=True), reply_markup=kb.ad_preview())


async def revise_ad(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        side = data.get("side", "sell")
        await set_state(session, user.user_id, states.AD_COIN_SELECT, data={"side": side}, stack=[states.AD_SIDE_SELECT])
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.COIN_SELECT, reply_markup=kb.coin_select(), parse_mode=ParseMode.HTML)


async def publish_ad(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        if not user or not all(data.get(key) for key in ["side", "coin", "chain", "funds_source", "rate", "amount", "payment_method"]):
            await callback.answer("Ad is incomplete. Please revise it.", show_alert=True)
            return

        ref_code = await unique_ref_code(session)
        ad = Ad(
            ref_code=ref_code,
            user_id=user.user_id,
            side=data["side"],
            coin=data["coin"],
            chain=data["chain"],
            funds_source=data["funds_source"],
            rate=Decimal(str(data["rate"])),
            amount=Decimal(str(data["amount"])),
            payment_method=data["payment_method"],
            dm_username=public_username(user),
        )
        session.add(ad)
        user.ads_posted_count += 1
        user.post_ad_cooldown_until = datetime.utcnow() + timedelta(seconds=settings().post_ad_cooldown_seconds)
        await clear_flow(session, user.user_id)
        await session.flush()

        await post_public_ad(callback, ad, data, public_username(user))
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.ad_published(ref_code), reply_markup=kb.persistent_menu(user))


async def post_public_ad(callback: CallbackQuery, ad: Ad, data: dict, username: str) -> None:
    dm_url = f"https://t.me/{username}" if not username.isdigit() else f"tg://user?id={username}"
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Message", url=dm_url)]])
    text = msg.ad_text(data, username, preview=False)
    failures: list[str] = []
    if settings().ads_channel_id:
        try:
            sent = await callback.bot.send_message(
                settings().ads_channel_id,
                text,
                reply_markup=markup,
                reply_to_message_id=6,
            )
            ad.channel_msg_id = sent.message_id
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            failures.append(f"channel: {exc}")
    if failures:
        await callback.message.answer("Ad was saved, but public posting needs admin attention: " + "; ".join(failures))


async def enter_safe_sell(message: Message, user: User) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        if user and user.is_locked:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_ACTION, reply_markup=kb.persistent_menu(user))
            return
        await set_state(session, user.user_id, states.EXPRESS_LANDING, data={}, stack=[states.IDLE])
        await send_tracked_menu_photo(
            session,
            message.bot,
            user.user_id,
            message.chat.id,
            safe_sell_banner_file(),
            msg.SAFE_SELL_LANDING,
            reply_markup=kb.express_landing(user.wallet_balance, settings().support_url),
        )


async def show_payment_modes(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        result = await session.execute(select(PaymentMode))
        modes = list(result.scalars().all())
        await transition(session, user.user_id, states.EXPRESS_PAYMENT_MODE, {}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.PAYMENT_MODE_SELECT, reply_markup=kb.payment_modes(modes))


async def set_express_mode(callback: CallbackQuery, user: User, payment_mode: str) -> None:
    async with session_scope() as session:
        mode = await session.get(PaymentMode, payment_mode)
        if mode and not mode.available:
            await callback.answer("This mode is currently unavailable.", show_alert=True)
            return
        tiers = await get_rate_tiers(session, payment_mode)
        await transition(session, user.user_id, states.EXPRESS_AMOUNT_INPUT, {"payment_mode": payment_mode, "tx_type": "express_sell"}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.exchange_rates(payment_mode, tiers), reply_markup=kb.quick_amount("express"))


async def handle_express_amount(message: Message, user: User, text: str) -> None:
    amount = parse_decimal(text)
    if amount is None or amount <= 0:
        async with session_scope() as session:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Enter a valid amount greater than 0.", reply_markup=kb.quick_amount("express"))
        return
    await process_express_amount(message, user, amount)


async def process_express_amount(message: Message, user: User, amount: Decimal) -> None:
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        payment_mode = data.get("payment_mode", "UPI")
        rate = await rate_for_amount(session, payment_mode, amount)
        if rate is None:
            tiers = await get_rate_tiers(session, payment_mode)
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.exchange_rates(payment_mode, tiers), reply_markup=kb.quick_amount("express"))
            return
        amount_inr = as_money(amount * rate)
        await transition(
            session,
            user.user_id,
            states.EXPRESS_TOKEN_SELECT,
            {"amount_usd": str(amount), "amount_inr": str(amount_inr), "rate": str(rate)},
            push=True,
        )
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.inr_preview(amount_inr), reply_markup=kb.token_select("express"))


async def set_express_token(callback: CallbackQuery, user: User, token: str) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.EXPRESS_CHAIN_SELECT, {"token": token}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.express_chain_select(token), reply_markup=kb.express_chains(token, "express"))


async def set_express_chain(callback: CallbackQuery, user: User, chain: str) -> None:
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        token = data.get("token", "USDT")
        address = deposit_address(settings(), token, chain)
        await transition(session, user.user_id, states.EXPRESS_DEPOSIT_ADDRESS, {"chain": chain, "deposit_address": address}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.deposit_instructions(token, chain, address), reply_markup=kb.check_payment())


async def request_screenshot(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        if bot_session.state == states.EXPRESS_DEPOSIT_ADDRESS:
            await transition(session, user.user_id, states.EXPRESS_AWAITING_SCREENSHOT, {}, push=True)
        elif bot_session.state == states.WALLET_DEPOSIT_ADDRESS:
            await transition(session, user.user_id, states.WALLET_AWAITING_SCREENSHOT, {}, push=True)
        else:
            await callback.answer("No payment is awaiting proof.", show_alert=True)
            return
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.SCREENSHOT_PROMPT)


async def open_wallet(message: Message, user: User) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        if user and user.is_locked:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_ACTION, reply_markup=kb.persistent_menu(user))
            return
        await set_state(session, user.user_id, states.WALLET_MENU, data={}, stack=[states.IDLE])
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.wallet(user.wallet_balance), reply_markup=kb.wallet_menu())


async def wallet_add(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.WALLET_ADD_AMOUNT, {"tx_type": "wallet_deposit", "payment_mode": "wallet"}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.WALLET_ADD_AMOUNT, reply_markup=kb.back())


async def handle_wallet_deposit_amount(message: Message, user: User, text: str) -> None:
    amount = parse_decimal(text)
    if amount is None or amount <= 0:
        async with session_scope() as session:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Enter a valid amount greater than 0.", reply_markup=kb.back())
        return
    async with session_scope() as session:
        await transition(
            session,
            user.user_id,
            states.WALLET_ADD_TOKEN,
            {"amount_usd": str(amount), "amount_inr": "0"},
            push=True,
        )
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Select Your Crypto Token 👇", reply_markup=kb.token_select("wallet"))


async def set_wallet_token(callback: CallbackQuery, user: User, token: str) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.WALLET_ADD_CHAIN, {"token": token}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.express_chain_select(token), reply_markup=kb.express_chains(token, "wallet"))


async def set_wallet_chain(callback: CallbackQuery, user: User, chain: str) -> None:
    async with session_scope() as session:
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        token = data.get("token", "USDT")
        address = deposit_address(settings(), token, chain)
        await transition(
            session,
            user.user_id,
            states.WALLET_DEPOSIT_ADDRESS,
            {"chain": chain, "deposit_address": address},
            push=True,
        )
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.deposit_instructions(token, chain, address), reply_markup=kb.check_payment())


async def wallet_withdraw(callback: CallbackQuery, user: User) -> None:
    async with session_scope() as session:
        await transition(session, user.user_id, states.WALLET_WITHDRAW_AMOUNT, {}, push=True)
        await delete_callback_message(callback)
        await callback.answer()
        await send_tracked_menu_message(session, callback.message.bot, user.user_id, callback.message.chat.id, msg.WITHDRAW_AMOUNT, reply_markup=kb.back())


async def handle_withdraw_amount(message: Message, user: User, text: str) -> None:
    amount = parse_decimal(text)
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        if not user:
            return
        if amount is None or amount <= 0 or amount > user.wallet_balance:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, f"Enter an amount up to your available balance: ${user.wallet_balance:.2f}", reply_markup=kb.back())
            return
        await transition(session, user.user_id, states.WALLET_WITHDRAW_DEST, {"withdraw_amount": str(amount)}, push=True)
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.WITHDRAW_DESTINATION, reply_markup=kb.back())


async def handle_withdraw_destination(message: Message, user: User, text: str) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        amount = Decimal(str(data.get("withdraw_amount", "0")))
        if not user or amount <= 0 or amount > user.wallet_balance:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Withdrawal amount is no longer available.", reply_markup=kb.persistent_menu(user))
            await clear_flow(session, user.user_id)
            return
        tx = Transaction(
            user_id=user.user_id,
            type="withdrawal",
            amount_usd=amount,
            amount_inr=Decimal("0"),
            withdrawal_destination=text,
            status="pending",
        )
        session.add(tx)
        user.is_locked = True
        await clear_flow(session, user.user_id)
        await session.flush()
        await notify_admin_review(message, user, tx)
        await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.withdraw_queued(tx.tx_id), reply_markup=kb.persistent_menu(user))


async def delete_callback_message(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


async def show_my_stats(message: Message, user: User) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        if not user:
            return
        if user.is_locked:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.LOCKED_STATS, reply_markup=kb.persistent_menu(user))
            return
        member_since = user.first_seen_at.strftime("%d %b, %Y")
        await send_tracked_menu_message(
            session,
            message.bot,
            user.user_id,
            message.chat.id,
            msg.my_stats(
                user.username or str(user.user_id),
                member_since,
                user.ads_posted_count,
                user.safe_sells_completed,
                user.safe_sell_volume,
            ),
            reply_markup=kb.persistent_menu(user),
        )


async def show_global_stats(message: Message) -> None:
    async with session_scope() as session:
        stats = await session.get(GlobalStats, 1)
        if not stats:
            stats = GlobalStats(id=1)
            session.add(stats)
            await session.flush()
        await reset_today_if_needed(session, stats, settings().timezone)
        await send_tracked_menu_message(
            session,
            message.bot,
            message.from_user.id if message.from_user else 0,
            message.chat.id,
            msg.global_stats(stats.total_safe_sold_amount, stats.today_safe_sold_amount, stats.total_deals_completed),
        )


async def render_state(message: Message, user: User, state: str) -> None:
    async with session_scope() as session:
        user = await session.get(User, user.user_id)
        bot_session = await get_or_create_session(session, user.user_id)
        data = session_data(bot_session)
        if state in {states.IDLE, states.OBJECTIVE_SELECT}:
            await send_welcome(message, user)
        elif state == states.AD_SIDE_SELECT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.OBJECTIVE, reply_markup=kb.objective(), parse_mode=ParseMode.HTML)
        elif state == states.AD_COIN_SELECT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.COIN_SELECT, reply_markup=kb.coin_select(), parse_mode=ParseMode.HTML)
        elif state == states.AD_CHAIN_SELECT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.chain_select(data.get("coin", "USDT")), reply_markup=kb.chains(data.get("coin", "USDT")))
        elif state == states.AD_FUNDS_SOURCE:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.FUNDS_SOURCE, reply_markup=kb.funds_source())
        elif state == states.AD_RATE_INPUT:
            source = data.get("funds_source", "Legit")
            band = c.AD_RATE_BANDS.get(source, (94.0, 102.0))
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.rate_input(source, band[0], band[1]), reply_markup=kb.back())
        elif state == states.AD_AMOUNT_INPUT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.AMOUNT_INPUT, reply_markup=kb.quick_amount("ad"))
        elif state == states.AD_PAYMENT_METHOD:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.PAYMENT_METHOD, reply_markup=kb.payment_methods())
        elif state == states.AD_PREVIEW:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.ad_text(data, public_username(user), preview=True), reply_markup=kb.ad_preview())
        elif state == states.EXPRESS_LANDING:
            await send_tracked_menu_photo(session, message.bot, user.user_id, message.chat.id, safe_sell_banner_file(), msg.SAFE_SELL_LANDING, reply_markup=kb.express_landing(user.wallet_balance, settings().support_url))
        elif state == states.EXPRESS_PAYMENT_MODE:
            result = await session.execute(select(PaymentMode))
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.PAYMENT_MODE_SELECT, reply_markup=kb.payment_modes(list(result.scalars().all())))
        elif state == states.EXPRESS_AMOUNT_INPUT:
            payment_mode = data.get("payment_mode", "UPI")
            tiers = await get_rate_tiers(session, payment_mode)
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.exchange_rates(payment_mode, tiers), reply_markup=kb.quick_amount("express"))
        elif state == states.EXPRESS_TOKEN_SELECT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.inr_preview(Decimal(str(data.get("amount_inr", "0")))), reply_markup=kb.token_select("express"))
        elif state == states.EXPRESS_CHAIN_SELECT:
            token = data.get("token", "USDT")
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.express_chain_select(token), reply_markup=kb.express_chains(token, "express"))
        elif state == states.EXPRESS_DEPOSIT_ADDRESS:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.deposit_instructions(data.get("token", "USDT"), data.get("chain", "BEP20"), data.get("deposit_address", "")), reply_markup=kb.check_payment())
        elif state == states.WALLET_MENU:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.wallet(user.wallet_balance), reply_markup=kb.wallet_menu())
        elif state == states.WALLET_ADD_AMOUNT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.WALLET_ADD_AMOUNT, reply_markup=kb.back())
        elif state == states.WALLET_ADD_TOKEN:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, "Select Your Crypto Token 👇", reply_markup=kb.token_select("wallet"))
        elif state == states.WALLET_ADD_CHAIN:
            token = data.get("token", "USDT")
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.express_chain_select(token), reply_markup=kb.express_chains(token, "wallet"))
        elif state == states.WALLET_DEPOSIT_ADDRESS:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.deposit_instructions(data.get("token", "USDT"), data.get("chain", "BEP20"), data.get("deposit_address", "")), reply_markup=kb.check_payment())
        elif state == states.WALLET_WITHDRAW_AMOUNT:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.WITHDRAW_AMOUNT, reply_markup=kb.back())
        elif state == states.WALLET_WITHDRAW_DEST:
            await send_tracked_menu_message(session, message.bot, user.user_id, message.chat.id, msg.WITHDRAW_DESTINATION, reply_markup=kb.back())
        else:
            await send_welcome(message, user)


async def notify_admin_review(message: Message, user: User, tx: Transaction) -> None:
    caption = admin_review_text(user, tx)
    destinations: list[int | str] = []
    if settings().admin_review_chat_id:
        destinations.append(settings().admin_review_chat_id)
    destinations.extend(settings().admin_ids)
    if not destinations:
        await message.answer("Admin review destination is not configured. Add ADMIN_REVIEW_CHAT_ID or ADMIN_IDS.")
        return
    for chat_id in destinations:
        try:
            if tx.proof_file_id:
                await message.bot.send_photo(chat_id, tx.proof_file_id, caption=caption, reply_markup=kb.admin_review(tx.tx_id))
            else:
                await message.bot.send_message(chat_id, caption, reply_markup=kb.admin_review(tx.tx_id))
        except (TelegramBadRequest, TelegramForbiddenError):
            continue


def admin_review_text(user: User, tx: Transaction) -> str:
    username = f"@{user.username}" if user.username else str(user.user_id)
    if tx.type == "withdrawal":
        return f"""🧾 Pending Withdrawal

TX: {tx.tx_id}
User: {username}
Telegram ID: {user.user_id}
Amount: ${tx.amount_usd:.2f}
Destination:
{tx.withdrawal_destination}"""
    return f"""🧾 Pending Verification

TX: {tx.tx_id}
Type: {tx.type}
User: {username}
Telegram ID: {user.user_id}
Token: {tx.coin}
Chain: {tx.chain}
Amount USD: ${tx.amount_usd:.2f}
Expected INR: ₹{tx.amount_inr:.2f}
Payment Mode: {tx.payment_mode}
Deposit Address:
{tx.deposit_address}"""


async def unique_ref_code(session) -> str:
    for _ in range(20):
        ref_code = random_code()
        result = await session.execute(select(Ad.ad_id).where(Ad.ref_code == ref_code))
        if result.scalar_one_or_none() is None:
            return ref_code
    return random_code(6)
